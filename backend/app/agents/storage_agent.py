# backend/app/agents/storage_agent.py
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from uuid import UUID

from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile, VideoMetadata, LyricAnalysis, EnrichedArtistData

logger = logging.getLogger(__name__)

class StorageAgent:
    """Agent responsible for all database operations with enhanced deduplication"""
    
    async def create_discovery_session(
        self,
        deps: PipelineDependencies,
        session_data: Dict[str, Any]
    ) -> bool:
        """Create a new discovery session"""
        try:
            result = deps.supabase.table("discovery_sessions").insert(session_data).execute()
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
            result = deps.supabase.table("discovery_sessions").update(
                update_data
            ).eq("id", session_id).execute()
            return result.data is not None
        except Exception as e:
            logger.error(f"Error updating discovery session: {e}")
            return False
            
    async def get_artist_by_channel_id(
        self,
        deps: PipelineDependencies,
        channel_id: str
    ) -> Optional[EnrichedArtistData]:
        """Get artist by YouTube channel ID for deduplication"""
        try:
            result = deps.supabase.table("artists").select("*").eq(
                "youtube_channel_id", channel_id
            ).execute()
            
            if result.data and len(result.data) > 0:
                artist_data = result.data[0]
                # Convert to EnrichedArtistData
                return self._convert_to_enriched_artist(artist_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching artist by channel ID: {e}")
            return None
            
    async def get_artist_by_spotify_id(
        self,
        deps: PipelineDependencies,
        spotify_id: str
    ) -> Optional[EnrichedArtistData]:
        """Get artist by Spotify ID for deduplication"""
        try:
            result = deps.supabase.table("artists").select("*").eq(
                "spotify_id", spotify_id
            ).execute()
            
            if result.data and len(result.data) > 0:
                artist_data = result.data[0]
                return self._convert_to_enriched_artist(artist_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching artist by Spotify ID: {e}")
            return None
            
    async def find_similar_artists(
        self,
        deps: PipelineDependencies,
        artist_name: str,
        threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """Find similar artists by name for fuzzy deduplication"""
        try:
            # Use case-insensitive search with similarity
            result = deps.supabase.table("artists").select("*").ilike(
                "name", f"%{artist_name}%"
            ).execute()
            
            if result.data:
                # Filter by similarity threshold
                similar_artists = []
                for artist in result.data:
                    similarity = self._calculate_name_similarity(
                        artist_name.lower(), 
                        artist.get('name', '').lower()
                    )
                    if similarity >= threshold:
                        artist['similarity_score'] = similarity
                        similar_artists.append(artist)
                
                # Sort by similarity
                similar_artists.sort(key=lambda x: x['similarity_score'], reverse=True)
                return similar_artists
            
            return []
            
        except Exception as e:
            logger.error(f"Error finding similar artists: {e}")
            return []
            
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two artist names"""
        # Simple character-based similarity
        # In production, use more sophisticated algorithms like Levenshtein distance
        if name1 == name2:
            return 1.0
        
        # Normalize names
        name1_normalized = ''.join(c for c in name1.lower() if c.isalnum())
        name2_normalized = ''.join(c for c in name2.lower() if c.isalnum())
        
        if name1_normalized == name2_normalized:
            return 0.95
        
        # Check if one contains the other
        if name1_normalized in name2_normalized or name2_normalized in name1_normalized:
            return 0.8
        
        # Basic character overlap
        common_chars = set(name1_normalized) & set(name2_normalized)
        total_chars = set(name1_normalized) | set(name2_normalized)
        
        if total_chars:
            return len(common_chars) / len(total_chars)
        
        return 0.0
    
    def _convert_to_enriched_artist(self, artist_data: Dict[str, Any]) -> EnrichedArtistData:
        """Convert database record to EnrichedArtistData model"""
        try:
            # Create ArtistProfile first
            profile = ArtistProfile(
                name=artist_data.get('name', ''),
                youtube_channel_id=artist_data.get('youtube_channel_id'),
                youtube_channel_name=artist_data.get('youtube_channel_name'),
                instagram_handle=artist_data.get('instagram_handle'),
                spotify_id=artist_data.get('spotify_id'),
                email=artist_data.get('email'),
                website=artist_data.get('website'),
                genres=artist_data.get('genres', []),
                location=artist_data.get('location'),
                bio=artist_data.get('bio'),
                avatar_url=artist_data.get('avatar_url'),  # New field
                lyrical_themes=artist_data.get('lyrical_themes', []),  # New field
                follower_counts=artist_data.get('follower_counts', {}),
                social_links=artist_data.get('social_links', {}),
                metadata=artist_data.get('metadata', {}),
                enrichment_score=artist_data.get('enrichment_score', 0.0),
                status=artist_data.get('status', 'discovered')
            )
            
            # Create EnrichedArtistData
            enriched = EnrichedArtistData(
                profile=profile,
                videos=[],  # Would need to fetch separately
                lyric_analyses=[],  # Would need to fetch separately
                discovery_metadata={
                    'discovery_date': artist_data.get('discovery_date'),
                    'last_updated': artist_data.get('last_updated'),
                    'database_id': artist_data.get('id')
                }
            )
            
            # Copy enrichment score to top level
            enriched.enrichment_score = profile.enrichment_score
            
            return enriched
            
        except Exception as e:
            logger.error(f"Error converting to EnrichedArtistData: {e}")
            raise
            
    async def store_video(
        self,
        deps: PipelineDependencies,
        video: VideoMetadata
    ) -> Optional[Dict[str, Any]]:
        """Store video metadata with deduplication"""
        try:
            # Check if video already exists
            existing = deps.supabase.table("videos").select("*").eq(
                "youtube_video_id", video.youtube_video_id
            ).execute()
            
            if existing.data:
                logger.info(f"Video already exists: {video.youtube_video_id}")
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
            
            result = deps.supabase.table("videos").insert(video_data).execute()
            
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
        """Store lyric analysis with deduplication"""
        try:
            # Check if analysis already exists for this video
            existing = deps.supabase.table("lyric_analyses").select("*").eq(
                "video_id", str(analysis.video_id)
            ).execute()
            
            if existing.data:
                logger.info(f"Lyric analysis already exists for video: {analysis.video_id}")
                return existing.data[0]
            
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
            
            result = deps.supabase.table("lyric_analyses").insert(analysis_data).execute()
            
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
            result = deps.supabase.table("artists").select("*").eq("id", artist_id).single().execute()
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
            result = deps.supabase.table("artists").select("*").eq(
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
            result = deps.supabase.table("artists").select("*").gte(
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
            result = deps.supabase.table("artists").select("*").ilike(
                "name", f"%{query}%"
            ).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error searching artists: {e}")
            return []
            
    async def store_artist_profile(
        self,
        deps: PipelineDependencies,
        artist: ArtistProfile
    ) -> Optional[Dict[str, Any]]:
        """Store or update artist profile with comprehensive deduplication"""
        try:
            # Multi-level deduplication check
            
            # 1. Check by YouTube channel ID
            if artist.youtube_channel_id:
                existing = await self.get_artist_by_channel_id(deps, artist.youtube_channel_id)
                if existing:
                    logger.info(f"Artist already exists with YouTube channel ID: {artist.youtube_channel_id}")
                    return await self._update_existing_artist(deps, existing, artist)
            
            # 2. Check by Spotify ID
            if artist.spotify_id:
                existing = await self.get_artist_by_spotify_id(deps, artist.spotify_id)
                if existing:
                    logger.info(f"Artist already exists with Spotify ID: {artist.spotify_id}")
                    return await self._update_existing_artist(deps, existing, artist)
            
            # 3. Check by similar name
            similar_artists = await self.find_similar_artists(deps, artist.name, threshold=0.85)
            if similar_artists:
                # Check if any have matching identifiers
                for similar in similar_artists:
                    if (similar.get('youtube_channel_id') == artist.youtube_channel_id or
                        similar.get('spotify_id') == artist.spotify_id):
                        logger.info(f"Found similar artist: {similar.get('name')}")
                        existing = self._convert_to_enriched_artist(similar)
                        return await self._update_existing_artist(deps, existing, artist)
            
            # No duplicates found, create new artist
            # Sanitize metadata to prevent deep nesting issues
            sanitized_metadata = self._sanitize_metadata(artist.metadata)
            sanitized_follower_counts = self._sanitize_json_data(artist.follower_counts)
            sanitized_social_links = self._sanitize_json_data(artist.social_links)
            
            artist_data = {
                "name": artist.name,
                "youtube_channel_id": artist.youtube_channel_id,
                "youtube_channel_name": artist.youtube_channel_name,
                "instagram_handle": artist.instagram_handle,
                "spotify_id": artist.spotify_id,
                "email": artist.email,
                "website": artist.website,
                "genres": artist.genres[:10] if artist.genres else [],  # Limit genres to prevent large arrays
                "location": artist.location,
                "bio": artist.bio[:2000] if artist.bio else None,  # Limit bio length
                "avatar_url": artist.avatar_url,  # New field
                "lyrical_themes": artist.lyrical_themes[:10] if artist.lyrical_themes else [],  # New field
                "follower_counts": sanitized_follower_counts,
                "social_links": sanitized_social_links,
                "metadata": sanitized_metadata,
                "enrichment_score": artist.enrichment_score,
                "status": artist.status,
                "discovery_date": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            
            result = deps.supabase.table("artists").insert(artist_data).execute()
            
            if result.data:
                logger.info(f"✅ Created new artist: {artist.name}")
                return result.data[0]
                
            return None
            
        except Exception as e:
            logger.error(f"Error storing artist profile: {e}")
            return None
    
    async def _update_existing_artist(
        self,
        deps: PipelineDependencies,
        existing: EnrichedArtistData,
        new_data: ArtistProfile
    ) -> Optional[Dict[str, Any]]:
        """Update existing artist with new data if it improves the profile"""
        try:
            db_id = existing.discovery_metadata.get('database_id')
            if not db_id:
                logger.error("No database ID found for existing artist")
                return None
            
            # Only update if new data has higher enrichment score or adds new information
            should_update = False
            update_data = {}
            
            # Check enrichment score
            if new_data.enrichment_score > existing.enrichment_score:
                should_update = True
                update_data["enrichment_score"] = new_data.enrichment_score
            
            # Check for new social media data
            if new_data.spotify_id and not existing.profile.spotify_id:
                should_update = True
                update_data["spotify_id"] = new_data.spotify_id
            
            if new_data.instagram_handle and not existing.profile.instagram_handle:
                should_update = True
                update_data["instagram_handle"] = new_data.instagram_handle
            
            if new_data.email and not existing.profile.email:
                should_update = True
                update_data["email"] = new_data.email
            
            # Update genres (merge)
            if new_data.genres:
                merged_genres = list(set(existing.profile.genres + new_data.genres))
                if len(merged_genres) > len(existing.profile.genres):
                    should_update = True
                    update_data["genres"] = merged_genres
            
            # Update follower counts (merge)
            if new_data.follower_counts:
                merged_followers = {**existing.profile.follower_counts, **new_data.follower_counts}
                if merged_followers != existing.profile.follower_counts:
                    should_update = True
                    update_data["follower_counts"] = merged_followers
            
            # Update social links (merge)
            if new_data.social_links:
                merged_social = {**existing.profile.social_links, **new_data.social_links}
                if merged_social != existing.profile.social_links:
                    should_update = True
                    update_data["social_links"] = merged_social
            
            # Update metadata (merge)
            if new_data.metadata:
                merged_metadata = {**existing.profile.metadata, **new_data.metadata}
                update_data["metadata"] = merged_metadata
            
            if should_update:
                update_data["last_updated"] = datetime.now().isoformat()
                
                result = deps.supabase.table("artists").update(
                    update_data
                ).eq("id", db_id).execute()
                
                if result.data:
                    logger.info(f"✅ Updated existing artist: {existing.profile.name}")
                    return result.data[0]
            else:
                logger.info(f"ℹ️ No updates needed for artist: {existing.profile.name}")
                # Return existing data
                return {
                    "id": db_id,
                    **existing.profile.dict()
                }
                
            return None
            
        except Exception as e:
            logger.error(f"Error updating existing artist: {e}")
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
            result = deps.supabase.table("artists").update(
                update_data
            ).eq("id", artist_id).execute()
            return result.data is not None
        except Exception as e:
            logger.error(f"Error updating artist profile: {e}")
            return False

    def _sanitize_metadata(self, metadata: Dict[str, Any], max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """Sanitize metadata to prevent deep nesting issues"""
        if current_depth >= max_depth:
            return {}
        
        sanitized = {}
        for key, value in metadata.items():
            if isinstance(value, dict) and current_depth < max_depth:
                sanitized[key] = self._sanitize_metadata(value, max_depth, current_depth + 1)
            elif isinstance(value, (str, int, float, bool)) or value is None:
                sanitized[key] = value
            elif isinstance(value, list):
                # Limit list length and sanitize elements
                sanitized[key] = [str(item)[:500] for item in value[:20]]  # Max 20 items, 500 chars each
            else:
                # Convert complex objects to strings
                sanitized[key] = str(value)[:1000]
        return sanitized

    def _sanitize_json_data(self, data: Dict[str, Any], max_depth: int = 2, current_depth: int = 0) -> Dict[str, Any]:
        """Sanitize JSON data to prevent deep nesting issues"""
        if current_depth >= max_depth:
            return {}
        
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, dict) and current_depth < max_depth:
                sanitized[key] = self._sanitize_json_data(value, max_depth, current_depth + 1)
            elif isinstance(value, (str, int, float, bool)) or value is None:
                sanitized[key] = value
            elif isinstance(value, list):
                # Convert lists to simple values
                sanitized[key] = len(value) if isinstance(value, list) else str(value)[:100]
            else:
                # Convert complex objects to strings
                sanitized[key] = str(value)[:100]
        return sanitized