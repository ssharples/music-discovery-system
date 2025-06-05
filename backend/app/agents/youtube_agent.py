# backend/app/agents/youtube_agent.py
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import asyncio

from app.core.config import settings
from app.core.dependencies import PipelineDependencies
from app.models.artist import VideoMetadata

logger = logging.getLogger(__name__)

# Create YouTube Discovery Agent
youtube_agent = Agent(
    model=OpenAIModel('deepseek-chat', provider=DeepSeekProvider()),
    system_prompt="""You are a YouTube music discovery specialist. Your role is to:
    1. Search for emerging music artists on YouTube
    2. Extract video metadata and channel information
    3. Identify potential music videos vs other content
    4. Retrieve video captions when available
    
    Focus on finding artists with:
    - Less than 100k views on recent videos
    - Music-related content (official videos, audio, performances)
    - English language content primarily
    - Recent uploads (last 30 days preferred)
    """
)

@youtube_agent.tool
async def search_youtube_videos(
    ctx: RunContext[PipelineDependencies],
    query: str = "official music video",
    max_results: int = 50,
    published_after: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Search YouTube for music videos"""
    try:
        youtube = build('youtube', 'v3', developerKey=ctx.deps.youtube_api_key)
        
        # Default to videos from last 7 days
        if not published_after:
            published_after = datetime.now() - timedelta(days=7)
            
        # Convert to UTC timezone-aware datetime if needed
        if published_after.tzinfo is None:
            published_after = published_after.replace(tzinfo=timezone.utc)
        else:
            published_after = published_after.astimezone(timezone.utc)
            
        # Format as RFC 3339 UTC timestamp
        published_after_str = published_after.strftime('%Y-%m-%dT%H:%M:%SZ')
            
        search_request = youtube.search().list(
            q=query,
            part='id,snippet',
            maxResults=max_results,
            type='video',
            videoCategoryId='10',  # Music category
            publishedAfter=published_after_str,
            order='date',
            regionCode='US',
            relevanceLanguage='en'
        )
        
        search_response = search_request.execute()
        
        video_ids = [item['id']['videoId'] for item in search_response['items']]
        
        # Get video statistics
        if video_ids:
            stats_request = youtube.videos().list(
                part='statistics,contentDetails',
                id=','.join(video_ids)
            )
            stats_response = stats_request.execute()
            
            # Merge statistics with search results
            stats_map = {item['id']: item for item in stats_response['items']}
            
            videos = []
            for item in search_response['items']:
                video_id = item['id']['videoId']
                stats = stats_map.get(video_id, {})
                
                video_data = {
                    'video_id': video_id,
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnails': item['snippet']['thumbnails'],
                    'view_count': int(stats.get('statistics', {}).get('viewCount', 0)),
                    'like_count': int(stats.get('statistics', {}).get('likeCount', 0)),
                    'comment_count': int(stats.get('statistics', {}).get('commentCount', 0)),
                    'duration': stats.get('contentDetails', {}).get('duration')
                }
                videos.append(video_data)
                
            return videos
            
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        raise

@youtube_agent.tool  
async def get_channel_info(
    ctx: RunContext[PipelineDependencies],
    channel_id: str
) -> Dict[str, Any]:
    """Get detailed YouTube channel information"""
    try:
        youtube = build('youtube', 'v3', developerKey=ctx.deps.youtube_api_key)
        
        request = youtube.channels().list(
            part='snippet,statistics,contentDetails',
            id=channel_id
        )
        response = request.execute()
        
        if response['items']:
            channel = response['items'][0]
            return {
                'channel_id': channel['id'],
                'title': channel['snippet']['title'],
                'description': channel['snippet']['description'],
                'custom_url': channel['snippet'].get('customUrl'),
                'published_at': channel['snippet']['publishedAt'],
                'subscriber_count': int(channel['statistics'].get('subscriberCount', 0)),
                'video_count': int(channel['statistics'].get('videoCount', 0)),
                'view_count': int(channel['statistics'].get('viewCount', 0)),
                'uploads_playlist': channel['contentDetails']['relatedPlaylists']['uploads']
            }
            
        return {}
        
    except Exception as e:
        logger.error(f"Channel info error: {e}")
        raise

@youtube_agent.tool
async def get_channel_videos(
    ctx: RunContext[PipelineDependencies],
    channel_id: str,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """Get recent videos from a YouTube channel"""
    try:
        youtube = build('youtube', 'v3', developerKey=ctx.deps.youtube_api_key)
        
        # First get the channel's uploads playlist
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()
        
        if not channel_response['items']:
            return []
            
        uploads_playlist = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Get videos from uploads playlist
        playlist_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist,
            maxResults=max_results
        ).execute()
        
        video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response['items']]
        
        # Get video details
        if video_ids:
            videos_response = youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(video_ids)
            ).execute()
            
            return [{
                'video_id': video['id'],
                'title': video['snippet']['title'],
                'description': video['snippet']['description'],
                'published_at': video['snippet']['publishedAt'],
                'view_count': int(video['statistics'].get('viewCount', 0)),
                'like_count': int(video['statistics'].get('likeCount', 0)),
                'duration': video['contentDetails']['duration'],
                'tags': video['snippet'].get('tags', [])
            } for video in videos_response['items']]
            
        return []
        
    except Exception as e:
        logger.error(f"Channel videos error: {e}")
        raise

@youtube_agent.tool
async def get_video_captions(
    ctx: RunContext[PipelineDependencies],
    video_id: str,
    languages: List[str] = ['en']
) -> Optional[str]:
    """Get video captions/transcripts"""
    try:
        # Try to get transcript
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                captions = transcript.fetch()
                
                # Combine all caption segments
                full_text = ' '.join([segment['text'] for segment in captions])
                return full_text
                
            except:
                continue
                
        # Try auto-generated captions if manual not available
        try:
            transcript = transcript_list.find_generated_transcript(languages)
            captions = transcript.fetch()
            full_text = ' '.join([segment['text'] for segment in captions])
            return full_text
        except:
            pass
            
        return None
        
    except Exception as e:
        logger.warning(f"Caption fetch error for {video_id}: {e}")
        return None

class YouTubeDiscoveryAgent:
    """YouTube discovery agent wrapper"""
    
    def __init__(self):
        self.agent = youtube_agent
        logger.info("YouTubeDiscoveryAgent initialized")
        
    async def discover_artists(
        self,
        deps: PipelineDependencies,
        query: str = "official music video",
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Discover new music artists on YouTube"""
        
        logger.info(f"🎵 YouTubeDiscoveryAgent.discover_artists called with query='{query}', max_results={max_results}")
        
        # Call YouTube search directly - bypassing pydantic-ai agent
        try:
            logger.info("🔧 Building YouTube API client...")
            youtube = build('youtube', 'v3', developerKey=deps.youtube_api_key)
            logger.info("✅ YouTube API client built successfully")
            
            # Default to videos from last 7 days
            published_after = datetime.now() - timedelta(days=7)
            logger.info(f"📅 Search period: videos after {published_after}")
            
            # Convert to UTC timezone-aware datetime if needed
            if published_after.tzinfo is None:
                published_after = published_after.replace(tzinfo=timezone.utc)
            else:
                published_after = published_after.astimezone(timezone.utc)
                
            # Format as RFC 3339 UTC timestamp
            published_after_str = published_after.strftime('%Y-%m-%dT%H:%M:%SZ')
            logger.info(f"⏰ Formatted timestamp: {published_after_str}")
                
            logger.info("🔍 Making YouTube search request...")
            search_request = youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=max_results,
                type='video',
                videoCategoryId='10',  # Music category
                publishedAfter=published_after_str,
                order='date',
                regionCode='US',
                relevanceLanguage='en'
            )
            
            search_response = search_request.execute()
            logger.info(f"✅ YouTube search completed. Found {len(search_response.get('items', []))} videos")
            
            video_ids = [item['id']['videoId'] for item in search_response['items']]
            logger.info(f"📋 Extracted {len(video_ids)} video IDs")
            
            # Get video statistics
            videos = []
            if video_ids:
                stats_request = youtube.videos().list(
                    part='statistics,contentDetails',
                    id=','.join(video_ids)
                )
                stats_response = stats_request.execute()
                
                # Merge statistics with search results
                stats_map = {item['id']: item for item in stats_response['items']}
                
                for item in search_response['items']:
                    video_id = item['id']['videoId']
                    stats = stats_map.get(video_id, {})
                    
                    video_data = {
                        'video_id': video_id,
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'channel_id': item['snippet']['channelId'],
                        'channel_title': item['snippet']['channelTitle'],
                        'published_at': item['snippet']['publishedAt'],
                        'thumbnails': item['snippet']['thumbnails'],
                        'view_count': int(stats.get('statistics', {}).get('viewCount', 0)),
                        'like_count': int(stats.get('statistics', {}).get('likeCount', 0)),
                        'comment_count': int(stats.get('statistics', {}).get('commentCount', 0)),
                        'duration': stats.get('contentDetails', {}).get('duration')
                    }
                    videos.append(video_data)
            
            # Filter for emerging artists (< 100k views)
            emerging_videos = [
                v for v in videos 
                if v['view_count'] < 100000 and v['view_count'] > 1000
            ]
            
            # Group by channel
            channels = {}
            for video in emerging_videos:
                channel_id = video['channel_id']
                if channel_id not in channels:
                    channels[channel_id] = {
                        'channel_id': channel_id,
                        'channel_title': video['channel_title'],
                        'videos': []
                    }
                channels[channel_id]['videos'].append(video)
                
            # Get additional channel info for promising artists
            enriched_channels = []
            for channel_id, channel_data in channels.items():
                # Only process channels with multiple videos or high engagement
                if len(channel_data['videos']) >= 1:  # Reduced threshold
                    try:
                        # Get channel info
                        channel_request = youtube.channels().list(
                            part='snippet,statistics,contentDetails',
                            id=channel_id
                        )
                        channel_response = channel_request.execute()
                        
                        if channel_response['items']:
                            channel = channel_response['items'][0]
                            channel_data['channel_info'] = {
                                'channel_id': channel['id'],
                                'title': channel['snippet']['title'],
                                'description': channel['snippet']['description'],
                                'custom_url': channel['snippet'].get('customUrl'),
                                'published_at': channel['snippet']['publishedAt'],
                                'subscriber_count': int(channel['statistics'].get('subscriberCount', 0)),
                                'video_count': int(channel['statistics'].get('videoCount', 0)),
                                'view_count': int(channel['statistics'].get('viewCount', 0)),
                                'uploads_playlist': channel['contentDetails']['relatedPlaylists']['uploads']
                            }
                            enriched_channels.append(channel_data)
                            
                    except Exception as e:
                        logger.warning(f"Could not get channel info for {channel_id}: {e}")
                        continue
                    
            return enriched_channels
            
        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            return []
        
    async def get_artist_videos_with_captions(
        self,
        deps: PipelineDependencies,
        channel_id: str,
        max_videos: int = 5
    ) -> List[Dict[str, Any]]:
        """Get artist videos with captions for analysis"""
        
        try:
            youtube = build('youtube', 'v3', developerKey=deps.youtube_api_key)
            
            # First get the channel's uploads playlist
            channel_response = youtube.channels().list(
                part='contentDetails',
                id=channel_id
            ).execute()
            
            if not channel_response['items']:
                return []
                
            uploads_playlist = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from uploads playlist
            playlist_response = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist,
                maxResults=max_videos
            ).execute()
            
            video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response['items']]
            
            # Get video details
            videos = []
            if video_ids:
                videos_response = youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(video_ids)
                ).execute()
                
                for video in videos_response['items']:
                    videos.append({
                        'video_id': video['id'],
                        'title': video['snippet']['title'],
                        'description': video['snippet']['description'],
                        'published_at': video['snippet']['publishedAt'],
                        'view_count': int(video['statistics'].get('viewCount', 0)),
                        'like_count': int(video['statistics'].get('likeCount', 0)),
                        'duration': video['contentDetails']['duration'],
                        'tags': video['snippet'].get('tags', [])
                    })
            
            # Get captions for each video
            videos_with_captions = []
            for video in videos:
                try:
                    # Try to get transcript
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video['video_id'])
                    
                    captions = None
                    for lang in ['en']:
                        try:
                            transcript = transcript_list.find_transcript([lang])
                            captions_data = transcript.fetch()
                            
                            # Combine all caption segments
                            captions = ' '.join([segment['text'] for segment in captions_data])
                            break
                            
                        except:
                            continue
                            
                    # Try auto-generated captions if manual not available
                    if not captions:
                        try:
                            transcript = transcript_list.find_generated_transcript(['en'])
                            captions_data = transcript.fetch()
                            captions = ' '.join([segment['text'] for segment in captions_data])
                        except:
                            pass
                    
                    video['captions'] = captions
                    video['captions_available'] = captions is not None
                    videos_with_captions.append(video)
                    
                except Exception as e:
                    logger.warning(f"Caption fetch error for {video['video_id']}: {e}")
                    video['captions'] = None
                    video['captions_available'] = False
                    videos_with_captions.append(video)
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.5)
                
            return videos_with_captions
            
        except Exception as e:
            logger.error(f"Channel videos error: {e}")
            return []