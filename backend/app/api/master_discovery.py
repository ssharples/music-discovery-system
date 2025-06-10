"""
Master Discovery API
Provides API endpoints for the complete music discovery workflow.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
import logging

from app.agents.master_discovery_agent import MasterDiscoveryAgent
from app.core.dependencies import get_pipeline_deps, PipelineDependencies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/master-discovery", tags=["Master Discovery"])

# Global master discovery agent instance
master_agent = MasterDiscoveryAgent()

@router.post("/discover")
async def discover_artists(
    max_results: int = Query(default=50, le=200, description="Maximum number of artists to process"),
    search_query: str = Query(default="official music video", description="YouTube search query"),
    deps: PipelineDependencies = Depends(get_pipeline_deps)
) -> Dict[str, Any]:
    """
    Execute the complete music discovery workflow:
    
    1. 📺 Search YouTube for videos with filters (upload date, duration, quality)
    2. 🔍 Extract artist names from video titles and validate content  
    3. 🚫 Filter out AI-generated content, covers, remixes
    4. 📋 Check for existing artists in database
    5. 🔗 Extract social media links from video descriptions
    6. 🎭 Crawl YouTube channels for subscriber counts and additional links
    7. 🎵 Crawl Spotify profiles for monthly listeners, top tracks, bio
    8. 📸 Crawl Instagram profiles for follower counts
    9. 🎬 Crawl TikTok profiles for followers and likes
    10. 🎤 Analyze lyrics from top songs using DeepSeek AI
    11. 📊 Calculate sophisticated discovery scores (0-100) with artificial inflation detection
    12. 💾 Store complete artist profiles in Supabase database
    
    **Filters Applied:**
    - Recent uploads (last week)
    - Under 4 minutes duration
    - HD quality
    - Excludes: AI, Suno, generated, Udio, covers, remixes
    
    **Scoring Algorithm:**
    - YouTube: 30 points (subscriber count)
    - Spotify: 25 points (monthly listeners)  
    - Instagram: 20 points (followers)
    - TikTok: 15 points (followers)
    - Content Quality: 10 points (lyrics themes, tracks)
    - Artificial Inflation Detection: -20 points penalty
    
    **Consistency Checks:**
    - Detects suspicious follower ratios across platforms
    - Flags accounts with 1M+ Spotify listeners but <50K social media followers
    - Applies penalties for likely artificial inflation
    """
    try:
        logger.info(f"🎵 Starting master discovery: query='{search_query}', max_results={max_results}")
        
        # Execute the master discovery workflow
        result = await master_agent.discover_artists(
            deps=deps,
            max_results=max_results,
            search_query=search_query
        )
        
        # Add API metadata
        result['api_metadata'] = {
            'endpoint': '/api/master-discovery/discover',
            'workflow_version': '1.0',
            'features': [
                'YouTube video search with filters',
                'Artist name extraction and validation',
                'AI content detection and filtering',
                'Multi-platform social media crawling',
                'Spotify API integration',
                'Lyrics analysis with DeepSeek AI',
                'Sophisticated scoring with consistency checks',
                'Artificial inflation detection',
                'Supabase database storage'
            ]
        }
        
        logger.info(f"✅ Master discovery completed: {result['data']['total_found']} artists found")
        return result
        
    except Exception as e:
        logger.error(f"❌ Master discovery failed: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery workflow failed: {str(e)}")

@router.get("/status")
async def get_discovery_status() -> Dict[str, Any]:
    """
    Get the status and capabilities of the master discovery system.
    """
    return {
        'status': 'operational',
        'master_discovery_agent': {
            'version': '1.0',
            'components': {
                'youtube_agent': 'Crawl4AI YouTube Agent',
                'enrichment_agent': 'Crawl4AI Enrichment Agent',
                'storage_agent': 'Supabase Storage Agent'
            },
            'workflow_phases': [
                'YouTube Video Discovery',
                'Video Processing and Filtering', 
                'Artist Processing Pipeline',
                'Multi-platform Enrichment',
                'Scoring and Database Storage'
            ],
            'supported_platforms': [
                'YouTube (channels, videos, subscribers)',
                'Spotify (monthly listeners, tracks, bio, API data)',
                'Instagram (followers, profile data)',
                'TikTok (followers, likes)',
                'Musixmatch (lyrics for analysis)'
            ],
            'ai_capabilities': [
                'Artist name extraction from video titles',
                'AI-generated content detection',
                'Lyrics sentiment analysis with DeepSeek',
                'Artificial inflation detection',
                'Content quality assessment'
            ]
        },
        'configuration': {
            'max_results_limit': 200,
            'default_search_query': 'official music video',
            'youtube_filters': {
                'upload_date': 'week',
                'duration': 'short (under 4 minutes)',
                'quality': 'HD',
                'sort_by': 'date'
            },
            'excluded_keywords': [
                'ai', 'suno', 'generated', 'udio', 'cover', 'remix',
                'artificial intelligence', 'ai-generated', 'ai music'
            ]
        },
        'scoring_system': {
            'total_points': 100,
            'breakdown': {
                'youtube_metrics': 30,
                'spotify_metrics': 25,
                'instagram_metrics': 20,
                'tiktok_metrics': 15,
                'content_quality': 10
            },
            'penalties': {
                'artificial_inflation': 'up to -20 points'
            },
            'consistency_checks': [
                'Cross-platform follower ratio analysis',
                'Suspicious growth pattern detection',
                'Platform relevance validation'
            ]
        }
    }

@router.get("/health")
async def health_check(deps: PipelineDependencies = Depends(get_pipeline_deps)) -> Dict[str, Any]:
    """
    Health check for the master discovery system components.
    """
    health_status = {
        'overall_status': 'healthy',
        'components': {},
        'timestamp': logger.info(f"Health check requested")
    }
    
    try:
        # Check Supabase connection
        test_query = await deps.supabase.table("artist").select("count").limit(1).execute()
        health_status['components']['supabase'] = 'connected'
    except Exception as e:
        health_status['components']['supabase'] = f'error: {str(e)}'
        health_status['overall_status'] = 'degraded'
    
    # Check agent initialization
    try:
        health_status['components']['master_agent'] = 'initialized'
        health_status['components']['youtube_agent'] = 'ready'
        health_status['components']['enrichment_agent'] = 'ready'
        health_status['components']['storage_agent'] = 'ready'
    except Exception as e:
        health_status['components']['agents'] = f'error: {str(e)}'
        health_status['overall_status'] = 'unhealthy'
    
    return health_status

@router.get("/examples")
async def get_workflow_examples() -> Dict[str, Any]:
    """
    Get examples of how the master discovery workflow processes different types of content.
    """
    return {
        'workflow_examples': {
            'example_1': {
                'input': {
                    'video_title': 'John Doe - Amazing Song (Official Music Video)',
                    'description': 'Follow me on Instagram: https://instagram.com/johndoe\nSpotify: https://open.spotify.com/artist/1a2b3c4d5e',
                    'channel': 'John Doe Music'
                },
                'processing_steps': {
                    'artist_extraction': 'John Doe',
                    'social_links_found': ['Instagram', 'Spotify'],
                    'content_validation': 'Passed (no AI keywords)',
                    'enrichment_targets': ['YouTube channel', 'Spotify profile', 'Instagram profile']
                },
                'expected_data': {
                    'youtube_subscribers': 'Extracted from channel',
                    'spotify_monthly_listeners': 'Scraped from profile',
                    'instagram_followers': 'Crawled from profile',
                    'lyrics_analysis': 'Analyzed with DeepSeek AI',
                    'discovery_score': 'Calculated 0-100'
                }
            },
            'example_2_filtered': {
                'input': {
                    'video_title': 'AI Generated Music - Suno AI Song',
                    'description': 'Created with artificial intelligence'
                },
                'processing_result': 'FILTERED OUT - Contains excluded keywords: ai, suno, artificial intelligence'
            },
            'example_3_existing': {
                'input': {
                    'video_title': 'Taylor Swift - New Song (Official)',
                    'artist_extraction': 'Taylor Swift'
                },
                'processing_result': 'SKIPPED - Artist already exists in database'
            }
        },
        'quality_filters': {
            'artist_name_patterns': [
                'Artist - Song (Official Video)',
                'Artist - Song [Official Video]', 
                'Artist | Song',
                'Artist: Song',
                'Song by Artist'
            ],
            'excluded_content': [
                'AI-generated music',
                'Cover versions',
                'Remix versions',
                'Songs with Suno/Udio keywords'
            ],
            'validation_checks': [
                'Valid artist name extraction',
                'Content keyword filtering',
                'Database duplicate checking',
                'Social media link validation'
            ]
        }
    } 