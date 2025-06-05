# backend/app/agents/storage_agent.py
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from uuid import UUID

from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile, VideoMetadata, LyricAnalysis

logger = logging.getLogger(__name__)

class StorageAgent:
    """Agent responsible for all database operations"""
    
    async def create_discovery_session(
        self,
        deps: PipelineDependencies,
        session_data: Dict[str, Any]
    ) -> bool:
        """Create a new discovery session"""
        try:
            result = await deps.supabase.table("discovery_sessions").insert(session_data).execute()
            return result.data is not None
        except Exception as e:
            logger.error(f"Error creating discovery session: {e}")
            return False
            
    async def update_discovery_session(
        self,
        deps: PipelineDependencies,
        session_id: str,
        update_data: Dict[str, Any]
    ) -> bool:
        """Update discovery session"""
        try:
            result = await deps.supabase.table("discovery_sessions").update(
                update_data
            ).eq("id", session_id).execute()
            return result.data is not None
        except Exception as e:
            logger.error(f"Error updating discovery session: {e}")
            return False
            
    async def store_video(
        self,
        deps: PipelineDependencies,
        video: VideoMetadata
    ) -> Optional[Dict[str, Any]]:
        """Store video metadata"""
        try:
            # Check if video already exists
            existing = await deps.supabase.table("videos").select("*").eq(
                "youtube_video_id", video.youtube_video_id
            ).execute()
            
            if existing.data:
                return existing.data[0]
                
            video_data = {
                "artist_id": str(video.artist_id),
                "youtube_video_id": video.youtube_video_id,
                "title": video.title,
                "description": video.description,
                "view_count": video.view_count,
                "like_count": video.like_count,
                "comment_count": video.comment_count,
                "published_at": video.published_at.isoformat() if video.published_at else None,
                "duration": video.duration,
                "tags": video.tags,
                "captions_available": video.captions_available,
                "metadata": video.metadata
            }
            
            result = await deps.supabase.table("videos").insert(video_data).execute()
            
            if result.data:
                return result.data[0]
                
            return None
            
        except Exception as e:
            logger.error(f"Error storing video: {e}")
            return None
            
    async def store_lyric_analysis(
        self,
        deps: PipelineDependencies,
        analysis: LyricAnalysis
    ) -> Optional[Dict[str, Any]]:
        """Store lyric analysis"""
        try:
            analysis_data = {
                "video_id": str(analysis.video_id),
                "artist_id": str(analysis.artist_id),
                "themes": analysis.themes,
                "sentiment_score": analysis.sentiment_score,
                "emotional_content": analysis.emotional_content,
                "lyrical_style": analysis.lyrical_style,
                "subject_matter": analysis.subject_matter,
                "language": analysis.language,
                "analysis_metadata": analysis.analysis_metadata
            }
            
            result = await deps.supabase.table("lyric_analyses").insert(analysis_data).execute()
            
            if result.data:
                return result.data[0]
                
            return None
            
        except Exception as e:
            logger.error(f"Error storing lyric analysis: {e}")
            return None
            
    async def get_artist_by_id(
        self,
        deps: PipelineDependencies,
        artist_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get artist by ID"""
        try:
            result = await deps.supabase.table("artists").select("*").eq("id", artist_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Error fetching artist: {e}")
            return None
            
    async def get_artists_by_status(
        self,
        deps: PipelineDependencies,
        status: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get artists by status"""
        try:
            result = await deps.supabase.table("artists").select("*").eq(
                "status", status
            ).range(offset, offset + limit - 1).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error fetching artists by status: {e}")
            return []
            
    async def get_high_value_artists(
        self,
        deps: PipelineDependencies,
        min_score: float = 0.7,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get high-value artists based on enrichment score"""
        try:
            result = await deps.supabase.table("artists").select("*").gte(
                "enrichment_score", min_score
            ).order("enrichment_score", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error fetching high-value artists: {e}")
            return []
            
    async def search_artists(
        self,
        deps: PipelineDependencies,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search artists by name"""
        try:
            result = await deps.supabase.table("artists").select("*").ilike(
                "name", f"%{query}%"
            ).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error searching artists: {e}")
            return []_artist_profile(
        self,
        deps: PipelineDependencies,
        artist: ArtistProfile
    ) -> Optional[Dict[str, Any]]:
        """Store or update artist profile"""
        try:
            # Check if artist already exists
            existing = await deps.supabase.table("artists").select("*").eq(
                "youtube_channel_id", artist.youtube_channel_id
            ).execute()
            
            artist_data = {
                "name": artist.name,
                "youtube_channel_id": artist.youtube_channel_id,
                "youtube_channel_name": artist.youtube_channel_name,
                "instagram_handle": artist.instagram_handle,
                "spotify_id": artist.spotify_id,
                "email": artist.email,
                "website": artist.website,
                "genres": artist.genres,
                "location": artist.location,
                "bio": artist.bio,
                "follower_counts": artist.follower_counts,
                "social_links": artist.social_links,
                "metadata": artist.metadata,
                "enrichment_score": artist.enrichment_score,
                "status": artist.status,
                "last_updated": datetime.now().isoformat()
            }
            
            if existing.data:
                # Update existing artist
                result = await deps.supabase.table("artists").update(
                    artist_data
                ).eq("id", existing.data[0]["id"]).execute()
                
                if result.data:
                    return result.data[0]
            else:
                # Insert new artist
                artist_data["discovery_date"] = datetime.now().isoformat()
                result = await deps.supabase.table("artists").insert(artist_data).execute()
                
                if result.data:
                    return result.data[0]
                    
            return None
            
        except Exception as e:
            logger.error(f"Error storing artist profile: {e}")
            return None
            
    async def update_artist_profile(
        self,
        deps: PipelineDependencies,
        artist_id: str,
        update_data: Dict[str, Any]
    ) -> bool:
        """Update artist profile"""
        try:
            update_data["last_updated"] = datetime.now().isoformat()
            result = await deps.supabase.table("artists").update(
                update_data
            ).eq("id", artist_id).execute()
            return result.data is not None
        except Exception as e:
            logger.error(f"Error updating artist profile: {e}")
            return False
            
    async def store