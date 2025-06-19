"""
Master Music Discovery Agent
Orchestrates the complete workflow from YouTube discovery to multi-platform enrichment and scoring.

This agent coordinates:
1. YouTube video search and filtering
2. Artist name extraction and validation
3. Social media link extraction from descriptions
4. YouTube channel crawling
5. Spotify profile and API integration
6. Instagram and TikTok crawling
7. Lyrics analysis with DeepSeek
8. Sophisticated scoring algorithm with consistency checks
9. Database storage in Supabase

Clean architecture connecting all existing agents properly.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
import urllib.parse

from app.agents.crawl4ai_youtube_agent import Crawl4AIYouTubeAgent
from app.agents.crawl4ai_enrichment_agent import Crawl4AIEnrichmentAgent
from app.core.dependencies import PipelineDependencies
from app.models.artist import ArtistProfile
from app.core.config import settings

# AI imports for DeepSeek-powered data cleaning
from app.agents.ai_data_cleaner import get_ai_cleaner, AIDataCleaner

# Enhanced logging
from app.core.logging_config import get_progress_logger

logger = logging.getLogger(__name__)

class MasterDiscoveryAgent:
    """
    Master agent that orchestrates the complete music discovery workflow.
    """
    
    def __init__(self):
        # Initialize all sub-agents
        self.youtube_agent = Crawl4AIYouTubeAgent()
        self.enrichment_agent = Crawl4AIEnrichmentAgent()
        
        # Initialize AI data cleaner
        self.ai_cleaner = get_ai_cleaner()
        
        # Configuration
        self.exclude_keywords = [
            'ai', 'suno', 'generated', 'udio', 'cover', 'remix', 'remastered',
            'artificial intelligence', 'ai-generated', 'ai music', 'ai created',
            'machine learning', 'neural', 'bot', 'automated', 'synthetic'
        ]
        
        # Well-known artists to exclude (indicates AI/cover content)
        self.well_known_artists = [
            'taylor swift', 'drake', 'ariana grande', 'justin bieber', 'billie eilish',
            'the weeknd', 'dua lipa', 'ed sheeran', 'post malone', 'olivia rodrigo',
            'harry styles', 'bad bunny', 'doja cat', 'lil nas x', 'travis scott',
            'kanye west', 'eminem', 'rihanna', 'beyoncé', 'adele', 'bruno mars',
            'coldplay', 'imagine dragons', 'maroon 5', 'twenty one pilots'
        ]
        
        self.max_results = 1000
        self.max_view_count = 50000  # 50k view limit
        
        logger.info("✅ Master Discovery Agent initialized")
    
    async def discover_artists(
        self,
        deps: PipelineDependencies,
        max_results: int = 100,
        search_query: str = "official music video"
    ) -> Dict[str, Any]:
        """
        Execute the complete discovery workflow.
        
        Args:
            deps: Pipeline dependencies
            max_results: Maximum number of artists to process
            search_query: YouTube search query
            
        Returns:
            Dictionary with discovery results and metadata
        """
        start_time = time.time()
        logger.info(f"🎵 Starting master discovery workflow (max_results: {max_results})")
        
        try:
            # Phase 1: YouTube Video Discovery with Infinite Scroll
            logger.info("📺 Phase 1: YouTube video discovery with infinite scroll")
            phase1_start = time.time()
            
            processed_videos = await self._search_and_filter_videos_with_infinite_scroll(deps, search_query)
            
            phase1_time = time.time() - phase1_start
            logger.info(f"✅ Phase 1 complete in {phase1_time:.1f}s", extra={'operation_time': phase1_time})
            
            if not processed_videos:
                return self._create_empty_result("No videos found that passed filtering", start_time)
            
            logger.info(f"✅ Found {len(processed_videos)} videos that passed all filters")
            
            # Phase 2: Artist Processing Pipeline
            logger.info("🎤 Phase 2: Artist processing pipeline")
            phase2_start = time.time()
            
            discovered_artists = []
            total_processed = 0
            
            # Create progress logger for artist processing
            progress_logger = get_progress_logger('app.agents.master_discovery_agent', min(len(processed_videos), max_results))
            
            for i, video_data in enumerate(processed_videos[:max_results], 1):
                try:
                    artist_start = time.time()
                    progress_logger.step(f"Processing artist {i}: {video_data.get('extracted_artist_name', 'Unknown')}")
                    
                    artist_result = await self._process_single_artist(deps, video_data)
                    
                    artist_time = time.time() - artist_start
                    
                    if artist_result and artist_result.get('success'):
                        discovered_artists.append(artist_result)
                        progress_logger.step(f"✅ Artist {i} processed successfully: {artist_result.get('name')} ⏱️ {artist_time:.1f}s")
                    else:
                        progress_logger.error(f"⚠️ Artist {i} processing failed or filtered out ⏱️ {artist_time:.1f}s")
                    
                    total_processed += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)  # Reduced from 1.0s
                    
                except Exception as e:
                    progress_logger.error(f"❌ Error processing artist {i}: {e}")
                    continue
            
            # Phase 3: Final Results
            phase2_time = time.time() - phase2_start
            execution_time = time.time() - start_time
            
            logger.info(f"✅ Phase 2 complete in {phase2_time:.1f}s", extra={'operation_time': phase2_time})
            logger.info(f"🎉 Discovery complete! Found {len(discovered_artists)} artists in {execution_time:.2f}s")
            
            return {
                'status': 'success',
                'message': f'Successfully discovered {len(discovered_artists)} artists',
                'data': {
                    'artists': discovered_artists,
                    'total_processed': total_processed,
                    'total_found': len(discovered_artists),
                    'execution_time': execution_time,
                    'phase_times': {
                        'phase1_filtering': phase1_time,
                        'phase2_processing': phase2_time
                    },
                    'discovery_metadata': {
                        'videos_after_filtering': len(processed_videos),
                        'success_rate': len(discovered_artists) / total_processed if total_processed > 0 else 0,
                        'average_score': sum(a.get('discovery_score', 0) for a in discovered_artists) / len(discovered_artists) if discovered_artists else 0
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"💥 Master discovery workflow failed: {e}")
            return {
                'status': 'error',
                'message': f'Discovery workflow failed: {str(e)}',
                'data': {
                    'artists': [],
                    'total_processed': 0,
                    'total_found': 0,
                    'execution_time': time.time() - start_time,
                    'error': str(e)
                }
            }
    
    async def _search_and_filter_videos_with_infinite_scroll(
        self,
        deps: PipelineDependencies,
        search_query: str,
        target_filtered_videos: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Single YouTube search with infinite scrolling until we have enough videos that pass filters.
        Much more efficient than multiple separate searches.
        
        Args:
            deps: Pipeline dependencies
            search_query: YouTube search query  
            target_filtered_videos: Minimum number of videos that must pass filters
            
        Returns:
            List of processed videos that passed all filters
        """
        filter_start_time = time.time()
        logger.info(f"🔄 Starting infinite scroll search - target: {target_filtered_videos} filtered videos")
        
        try:
            # YouTube infinite scroll search
            logger.info(f"🔍 Performing infinite scroll search for: '{search_query}'")
            scroll_start = time.time()
            
            search_result = await self.youtube_agent.search_videos_with_infinite_scroll(search_query)
            
            scroll_time = time.time() - scroll_start
            
            if not search_result.success:
                logger.error(f"❌ Infinite scroll search failed: {search_result.error_message}")
                return []
            
            videos = search_result.videos
            logger.info(f"✅ Infinite scroll found {len(videos)} raw videos ⏱️ {scroll_time:.1f}s")
            
            # DEBUG: Log sample of found videos
            if videos:
                logger.info("🔍 Sample of found videos:")
                for i, video in enumerate(videos[:3]):
                    logger.info(f"  {i+1}. {getattr(video, 'title', 'No title')[:80]}...")
                    logger.info(f"     Channel: {getattr(video, 'channel_name', 'No channel')}")
                    logger.info(f"     Views: {getattr(video, 'view_count', 'No views')}")
            else:
                logger.warning("❌ No videos found from YouTube search")
            
            # Initialize filtering statistics
            stats = {
                'total_videos': len(videos),
                'passed_title_filter': 0,
                'passed_artist_extraction': 0,
                'passed_database_checks': 0,
                'passed_content_validation': 0,
                'found_social_in_description': 0,
                'found_social_via_channel_fallback': 0,
                'failed_social_requirement': 0,
                'final_success': 0
            }
            
            logger.info(f"🔍 Processing and filtering {len(videos)} videos...")
            filter_process_start = time.time()
            
            processed_videos = []
            
            # Create progress logger for filtering
            progress_logger = get_progress_logger('app.agents.master_discovery_agent.filtering', len(videos))
            
            for i, video in enumerate(videos, 1):
                video_start_time = time.time()
                video_title = getattr(video, 'title', 'Unknown')
                video_id = getattr(video, 'video_id', 'Unknown')
                
                try:
                    progress_logger.debug(f"🔍 Processing video {i}: '{video_title[:50]}...'")
                    
                    # Step 1: Title validation
                    step_start = time.time()
                    if not self._validate_title_contains_search_terms(video_title):
                        step_time = time.time() - step_start
                        progress_logger.debug(f"❌ Video {i} failed title filter ⏱️ {step_time:.3f}s")
                        logger.info(f"DEBUG: Video '{video_title}' failed title validation")
                        continue
                    
                    stats['passed_title_filter'] += 1
                    step_time = time.time() - step_start
                    progress_logger.debug(f"✅ Video {i} passed title filter ⏱️ {step_time:.3f}s")
                    
                    # Step 2: Artist name extraction and cleaning
                    step_start = time.time()
                    artist_name = await self._extract_and_clean_artist_name(video_title)
                    
                    if not artist_name:
                        step_time = time.time() - step_start
                        progress_logger.debug(f"❌ Video {i} failed artist extraction ⏱️ {step_time:.3f}s")
                        continue
                        
                    stats['passed_artist_extraction'] += 1
                    step_time = time.time() - step_start
                    progress_logger.debug(f"✅ Video {i} extracted artist: '{artist_name}' ⏱️ {step_time:.3f}s")
                    
                    # Step 3: Database duplicate checks
                    step_start = time.time()
                    if await self._artist_exists_in_database(deps, artist_name):
                        step_time = time.time() - step_start
                        progress_logger.debug(f"⏭️ Video {i} skipped - artist '{artist_name}' already exists ⏱️ {step_time:.3f}s")
                        continue
                    
                    if await self._video_exists_in_database(deps, getattr(video, 'url', '')):
                        step_time = time.time() - step_start
                        progress_logger.debug(f"⏭️ Video {i} skipped - video already processed ⏱️ {step_time:.3f}s")
                        continue
                        
                    stats['passed_database_checks'] += 1
                    step_time = time.time() - step_start
                    progress_logger.debug(f"✅ Video {i} passed database checks ⏱️ {step_time:.3f}s")
                    
                    # Step 4: View count filtering  
                    step_start = time.time()
                    view_count = getattr(video, 'view_count', 0)
                    if not self._validate_view_count(view_count):
                        step_time = time.time() - step_start
                        progress_logger.debug(f"❌ Video {i} failed view count filter ({view_count:,} views) ⏱️ {step_time:.3f}s")
                        continue
                    
                    # Step 5: English language validation
                    if not self._validate_english_language(artist_name):
                        step_time = time.time() - step_start
                        progress_logger.debug(f"❌ Video {i} failed English validation ⏱️ {step_time:.3f}s")
                        continue
                    
                    # Step 6: Well-known artist check
                    if self._is_well_known_artist(artist_name):
                        step_time = time.time() - step_start
                        progress_logger.debug(f"❌ Video {i} filtered - well-known artist '{artist_name}' ⏱️ {step_time:.3f}s")
                        continue

                    # Step 7: Enhanced content validation + FULL description retrieval
                    description = getattr(video, 'description', '')
                    
                    # CRITICAL FIX: If we only have a snippet, crawl the full video page
                    if not description or len(description) < 100 or 'snippet' in description.lower():
                        progress_logger.debug(f"🔍 Video {i} has limited description ('{description[:50]}...'), crawling full video page...")
                        try:
                            full_video_data = await self._get_full_video_description(video.url)
                            if full_video_data and full_video_data.get('description'):
                                description = full_video_data['description']
                                progress_logger.debug(f"✅ Video {i} retrieved full description ({len(description)} chars)")
                            else:
                                progress_logger.debug(f"⚠️ Video {i} failed to get full description")
                        except Exception as e:
                            progress_logger.debug(f"⚠️ Video {i} error getting full description: {e}")
                    
                    if not self._validate_content(video_title, description):
                        step_time = time.time() - step_start
                        progress_logger.debug(f"❌ Video {i} failed content validation ⏱️ {step_time:.3f}s")
                        continue
                        
                    stats['passed_content_validation'] += 1
                    step_time = time.time() - step_start
                    progress_logger.debug(f"✅ Video {i} passed all validation checks ⏱️ {step_time:.3f}s")
                    
                    # Step 8: Social media link extraction (NOW WITH FULL DESCRIPTIONS)
                    step_start = time.time()
                    progress_logger.debug(f"🔍 Video {i} extracting social links from full description ({len(description)} chars)...")
                    
                    raw_social_links = self._extract_social_links_from_description(description)
                    social_links = await self._clean_social_links(raw_social_links) if raw_social_links else None
                    social_source = "description"
                    
                    # Check if we have required social platforms
                    has_required_social = False
                    if social_links:
                        has_required_social = any(getattr(social_links, platform, None) for platform in ['spotify', 'instagram', 'tiktok'])
                        if has_required_social:
                            stats['found_social_in_description'] += 1
                            social_extraction_time = time.time() - step_start
                            progress_logger.debug(f"✅ Video {i} found social links in description: {[p for p in ['spotify', 'instagram', 'tiktok'] if getattr(social_links, p, None)]} ⏱️ {social_extraction_time:.3f}s")
                    
                    if not has_required_social:
                        progress_logger.debug(f"🔍 Video {i} no social links in description - trying channel fallback...")
                        
                        # Fallback: Try to extract social links from YouTube channel About page
                        try:
                            channel_social_links = await self._extract_social_from_channel(getattr(video, 'channel_url', None))
                            if channel_social_links:
                                progress_logger.debug(f"✅ Video {i} found social links from channel: {list(channel_social_links.keys())}")
                                
                                # Merge channel links with description links
                                if not social_links:
                                    social_links = await self._clean_social_links(channel_social_links)
                                else:
                                    # Update existing social_links object with channel findings
                                    for platform, url in channel_social_links.items():
                                        if not getattr(social_links, platform, None):
                                            setattr(social_links, platform, url)
                                
                                # Re-check if we now have required social links
                                has_required_social = any(getattr(social_links, platform, None) for platform in ['spotify', 'instagram', 'tiktok'])
                                if has_required_social:
                                    social_source = "channel_fallback"
                                    stats['found_social_via_channel_fallback'] += 1
                        except Exception as e:
                            progress_logger.debug(f"⚠️ Video {i} channel social link extraction failed: {e}")
                    
                    # Final check: STRICT social media requirement
                    if not has_required_social:
                        step_time = time.time() - step_start
                        progress_logger.debug(f"❌ Video {i} REJECTED - no required social links (Instagram, TikTok, Spotify) ⏱️ {step_time:.3f}s")
                        stats['failed_social_requirement'] += 1
                        continue  # Skip videos without required social links
                    
                    step_time = time.time() - step_start
                    
                    cleaned_links_dict = {
                        k: v for k, v in {
                            'instagram': getattr(social_links, 'instagram', None),
                            'tiktok': getattr(social_links, 'tiktok', None),
                            'spotify': getattr(social_links, 'spotify', None),
                            'twitter': getattr(social_links, 'twitter', None),
                            'facebook': getattr(social_links, 'facebook', None),
                            'youtube': getattr(social_links, 'youtube', None),
                            'website': getattr(social_links, 'website', None)
                        }.items() if v
                    }
                    
                    video_total_time = time.time() - video_start_time
                    progress_logger.step(f"✅ Video {i} PASSED ALL FILTERS: '{artist_name}' has social links ({social_source}): {list(cleaned_links_dict.keys())} ⏱️ Total: {video_total_time:.3f}s")
                    
                    # Convert video dataclass to dict and add processed data
                    video_dict = {
                        'title': video.title,
                        'url': video.url,
                        'channel_name': video.channel_name,
                        'view_count': video.view_count,
                        'duration': video.duration,
                        'upload_date': video.upload_date,
                        'video_id': video.video_id,
                        'thumbnail': getattr(video, 'thumbnail', None),
                        'description': getattr(video, 'description', ''),
                        'channel_url': getattr(video, 'channel_url', None),
                        'channel_id': getattr(video, 'channel_id', None),
                        'extracted_artist_name': artist_name,
                        'social_links': cleaned_links_dict,
                        'social_source': social_source  # Track where social links came from
                    }
                    
                    processed_videos.append(video_dict)
                    stats['final_success'] += 1
                    
                    # Stop if we've reached our target
                    if len(processed_videos) >= target_filtered_videos:
                        progress_logger.step(f"🎯 Reached target! {len(processed_videos)} videos passed all filters")
                        break
                    
                except Exception as e:
                    video_time = time.time() - video_start_time
                    progress_logger.error(f"❌ Video {i} processing error: {e} ⏱️ {video_time:.3f}s")
                    continue
            
            # Log comprehensive filtering statistics
            filter_process_time = time.time() - filter_process_start
            total_time = time.time() - filter_start_time
            
            logger.info(f"📊 FILTERING STATISTICS SUMMARY:")
            logger.info(f"   🎬 Total videos scraped: {stats['total_videos']}")
            logger.info(f"   📝 Passed title filter: {stats['passed_title_filter']} ({stats['passed_title_filter']/stats['total_videos']*100:.1f}%)")
            logger.info(f"   🎤 Passed artist extraction: {stats['passed_artist_extraction']} ({stats['passed_artist_extraction']/stats['total_videos']*100:.1f}%)")
            logger.info(f"   💾 Passed database checks: {stats['passed_database_checks']} ({stats['passed_database_checks']/stats['total_videos']*100:.1f}%)")
            logger.info(f"   ✅ Passed content validation: {stats['passed_content_validation']} ({stats['passed_content_validation']/stats['total_videos']*100:.1f}%)")
            logger.info(f"   🔗 Found social in description: {stats['found_social_in_description']}")
            logger.info(f"   🔗 Found social via channel fallback: {stats['found_social_via_channel_fallback']}")
            logger.info(f"   ❌ Failed social requirement: {stats['failed_social_requirement']}")
            logger.info(f"   🎯 FINAL SUCCESS: {stats['final_success']} ({stats['final_success']/stats['total_videos']*100:.1f}%)")
            logger.info(f"⏱️ Filtering times: Process: {filter_process_time:.1f}s, Total: {total_time:.1f}s")
            logger.info(f"🏁 Infinite scroll filtering complete: {len(processed_videos)} videos passed all filters")
            
            return processed_videos
            
        except asyncio.TimeoutError:
            logger.error("⏰ Infinite scroll search timed out after 5 minutes")
            return []
        except Exception as e:
            logger.error(f"❌ Infinite scroll search failed: {e}")
            return []
    
    async def _process_single_artist(
        self,
        deps: PipelineDependencies,
        video_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single artist through the complete enrichment pipeline.
        """
        artist_name = video_data.get('extracted_artist_name')
        if not artist_name:
            return None
        
        try:
            # Step 1: Create basic artist profile
            artist_profile = self._create_artist_profile(video_data)
            
            # Step 2: Crawl YouTube channel for additional data
            youtube_data = await self._crawl_youtube_channel(video_data)
            
            # Step 3: Multi-platform enrichment using Crawl4AI enrichment agent
            # Merge any social links found from YouTube channel crawling
            if youtube_data.get('social_links_from_channel'):
                for platform, url in youtube_data['social_links_from_channel'].items():
                    if platform not in artist_profile.social_links:
                        artist_profile.social_links[platform] = url
                        logger.info(f"🔗 Added {platform} link from YouTube channel: {url}")
            
            enriched_data = await self.enrichment_agent.enrich_artist(artist_profile)
            
            # Step 3.5: Enhanced social media discovery if initial enrichment failed
            if (not enriched_data.profile.social_links.get('instagram') and 
                not enriched_data.profile.social_links.get('tiktok') and
                video_data.get('url')):
                logger.info(f"🔍 Initial enrichment found limited social links, trying enhanced discovery for: {artist_name}")
                try:
                    from app.agents.crawl4ai_agent import Crawl4AIAgent
                    enhanced_agent = Crawl4AIAgent()
                    enhanced_results = await enhanced_agent.discover_artist_social_profiles(artist_name, video_data['url'])
                    
                    # Merge enhanced results with existing data
                    for platform, url in enhanced_results.get('profiles', {}).items():
                        if url and not enriched_data.profile.social_links.get(platform):
                            enriched_data.profile.social_links[platform] = url
                            logger.info(f"✅ Enhanced discovery found {platform}: {url}")
                            
                except Exception as e:
                    logger.warning(f"⚠️ Enhanced social media discovery failed: {e}")
            
            # Step 4: Spotify API integration for additional data
            spotify_api_data = await self._get_spotify_api_data(artist_profile.name)
            
            # Step 4.5: Merge Spotify API data into enriched_data
            if spotify_api_data:
                # Merge avatar URL if not already present
                if spotify_api_data.get('avatar_url') and not enriched_data.profile.avatar_url:
                    enriched_data.profile.avatar_url = spotify_api_data['avatar_url']
                    logger.info(f"✅ Added Spotify avatar URL: {spotify_api_data['avatar_url']}")
                
                # Merge genres if not already present or if Spotify has more genres
                if spotify_api_data.get('genres'):
                    if not enriched_data.profile.genres:
                        enriched_data.profile.genres = spotify_api_data['genres']
                        logger.info(f"✅ Added Spotify genres: {spotify_api_data['genres']}")
                    else:
                        # Merge unique genres from both sources
                        current_genres = set(enriched_data.profile.genres)
                        spotify_genres = set(spotify_api_data['genres'])
                        merged_genres = list(current_genres.union(spotify_genres))
                        enriched_data.profile.genres = merged_genres
                        logger.info(f"✅ Merged genres - Total: {len(merged_genres)}, Added from Spotify: {list(spotify_genres - current_genres)}")
                
                # Store Spotify API data in metadata for database storage
                if not enriched_data.profile.metadata:
                    enriched_data.profile.metadata = {}
                enriched_data.profile.metadata['spotify_api_data'] = {
                    'followers': spotify_api_data.get('followers', 0),
                    'popularity': spotify_api_data.get('popularity', 0),
                    'top_tracks': spotify_api_data.get('top_tracks', [])
                }
                logger.info(f"✅ Stored Spotify API metadata: {spotify_api_data.get('followers', 0)} followers, popularity {spotify_api_data.get('popularity', 0)}")
            
            # Step 5: Extract lyrics and analyze themes
            top_tracks = []
            if hasattr(enriched_data, 'profile') and hasattr(enriched_data.profile, 'metadata'):
                top_tracks = enriched_data.profile.metadata.get('top_tracks', [])
            
            lyrics_data = {}
            lyrical_analysis = ""
            if top_tracks:
                lyrics_data = await self._extract_lyrics_from_musixmatch(artist_profile.name, top_tracks)
                if lyrics_data:
                    lyrical_analysis = await self._analyze_lyrics_with_deepseek(lyrics_data, artist_profile.name)
            
            # Step 6: Calculate sophisticated discovery score
            discovery_score = self._calculate_discovery_score(
                youtube_data, enriched_data, spotify_api_data
            )
            
            # Step 7: Store in database
            artist_record = await self._store_artist_in_database(
                deps, artist_profile, enriched_data, youtube_data, 
                spotify_api_data, discovery_score, lyrical_analysis
            )
            
            if artist_record:
                return {
                    'success': True,
                    'name': artist_name,
                    'artist_id': artist_record.get('id'),
                    'discovery_score': discovery_score,
                    'youtube_data': youtube_data,
                    'enriched_data': enriched_data.to_dict() if hasattr(enriched_data, 'to_dict') else str(enriched_data),
                    'spotify_api_data': spotify_api_data
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Error processing artist {artist_name}: {e}")
            return None
    
    def _extract_artist_name(self, title: str) -> Optional[str]:
        """
        Extract artist name from video title using comprehensive patterns.
        Excludes featured artists and collaborations.
        """
        if not title:
            return None
        
        # Log the title being processed for debugging
        logger.debug(f"🎯 Extracting artist from title: '{title}'")
        
        # Common patterns for music video titles (ordered by specificity)
        patterns = [
            # Official video patterns
            r'^([^-]+?)\s*-\s*[^-]+?\s*\(Official\s*(?:Music\s*)?Video\)',  # Artist - Song (Official Video)
            r'^([^-]+?)\s*-\s*[^-]+?\s*\[Official\s*(?:Music\s*)?Video\]',  # Artist - Song [Official Video]
            r'^([^-]+?)\s*-\s*[^-]+?\s*\|\s*Official\s*(?:Music\s*)?Video',  # Artist - Song | Official Video
            
            # Comma separated patterns
            r'^([^,]+?),\s*([^,]+?)\s*-\s*([^,\(]+)',  # Artist1, Artist2 - Song
            
            # Basic separator patterns
            r'^([^-]+?)\s*-\s*[^-]+$',  # Artist - Song
            r'^([^|]+?)\s*\|\s*[^|]+$',  # Artist | Song
            r'^([^:]+?):\s*[^:]+$',     # Artist: Song
            
            # Quote patterns
            r'^(.+?)\s*["\']([^"\']+)["\']',  # Artist "Song"
            
            # By patterns
            r'^(.+?)\s*(?:by|BY)\s+(.+?)(?:\s*\(|$)',  # Song by Artist
            
            # Parentheses patterns
            r'^([^(]+?)\s*\([^)]*(?:official|music|video|mv)[^)]*\)',  # Artist (Official Video)
            
            # Last resort - take everything before common keywords
            r'^([^(]+?)(?:\s*\((?:official|music|video|mv|lyric|audio))',  # Artist (keyword)
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, title.strip(), re.IGNORECASE)
            if match:
                logger.debug(f"🎯 Pattern {i+1} matched: {pattern}")
                # Try both groups for patterns with multiple captures
                for group_idx in [1, 2]:
                    try:
                        artist_name = match.group(group_idx).strip()
                        logger.debug(f"🎯 Extracted candidate: '{artist_name}' from group {group_idx}")
                        if artist_name and self._is_valid_artist_name(artist_name):
                            # Clean and remove featured artists
                            cleaned_name = self._clean_artist_name(artist_name)
                            final_name = self._remove_featured_artists(cleaned_name)
                            logger.debug(f"✅ Final artist name: '{final_name}'")
                            return final_name
                        else:
                            logger.debug(f"❌ Invalid artist name: '{artist_name}'")
                    except IndexError:
                        continue
        
        # Fallback: take first part before common separators
        for separator in [' - ', ' | ', ': ', ' (', ' [', ' feat', ' ft']:
            if separator in title:
                potential_artist = title.split(separator)[0].strip()
                if self._is_valid_artist_name(potential_artist):
                    cleaned_name = self._clean_artist_name(potential_artist)
                    return self._remove_featured_artists(cleaned_name)
        
        return None
    
    def _is_valid_artist_name(self, name: str) -> bool:
        """
        Check if extracted text is a valid artist name.
        """
        if not name or len(name.strip()) < 2:
            return False
        
        name_lower = name.lower().strip()
        
        # Common non-artist terms
        invalid_terms = [
            'official', 'music', 'video', 'audio', 'lyric', 'lyrics',
            'feat', 'featuring', 'ft', 'remix', 'cover', 'live',
            'new', 'latest', 'best', 'top', 'album', 'single',
            'song', 'track', 'ep', 'mixtape', 'full', 'hd', 'hq',
            'youtube', 'vevo', 'records', 'entertainment'
        ]
        
        # Check if the name is just common terms
        if name_lower in invalid_terms:
            return False
        
        # Check for excessive length
        if len(name) > 50:
            return False
        
        # Check for numbers/years that suggest it's not an artist name
        if re.match(r'^\d{4}$', name.strip()):  # Just a year
            return False
        
        return True
    
    def _clean_artist_name(self, name: str) -> str:
        """
        Clean and normalize artist name.
        """
        # Remove common prefixes/suffixes
        name = re.sub(r'\s*\((Official|Music|Video|HD|4K)\).*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(ft\.|feat\.|featuring).*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(Official|Music|Video).*$', '', name, flags=re.IGNORECASE)
        
        return name.strip()
    
    def _remove_featured_artists(self, name: str) -> str:
        """
        Remove featured artists and collaborations from artist name.
        Returns only the main artist.
        """
        if not name:
            return name
        
        # Patterns for featured artists and collaborations
        feature_patterns = [
            r'\s*(?:feat\.|featuring|ft\.)\s+.+$',  # feat. Artist, featuring Artist, ft. Artist
            r'\s*(?:with|w/)\s+.+$',               # with Artist, w/ Artist
            r'\s*(?:vs\.?|versus)\s+.+$',          # vs Artist, versus Artist
            r'\s*(?:&|\+|and)\s+[A-Z].+$',        # & Artist, + Artist, and Artist (only if next word is capitalized)
            r'\s*(?:x|X)\s+[A-Z].+$',             # x Artist, X Artist (collaborations)
            r'\s*,\s*[A-Z].+$',                    # , Artist (comma separated)
        ]
        
        cleaned_name = name
        for pattern in feature_patterns:
            cleaned_name = re.sub(pattern, '', cleaned_name, flags=re.IGNORECASE)
        
        # Clean up any trailing punctuation or whitespace
        cleaned_name = re.sub(r'[,\s]+$', '', cleaned_name).strip()
        
        # If we removed everything, return the original
        if not cleaned_name or len(cleaned_name) < 2:
            return name
        
        logger.debug(f"Cleaned artist name: '{name}' -> '{cleaned_name}'")
        return cleaned_name
    
    async def _artist_exists_in_database(self, deps: PipelineDependencies, artist_name: str) -> bool:
        """
        Check if artist already exists in Supabase database using exact and fuzzy matching.
        """
        try:
            # First try exact match
            exact_response = deps.supabase.table("artists").select("id").eq("name", artist_name).execute()
            if len(exact_response.data) > 0:
                logger.debug(f"Found exact match for artist: {artist_name}")
                return True
            
            # Then try fuzzy match with cleaned names
            cleaned_name = self._clean_artist_name(artist_name).lower()
            fuzzy_response = deps.supabase.table("artists").select("id", "name").execute()
            
            for existing_artist in fuzzy_response.data:
                existing_cleaned = self._clean_artist_name(existing_artist['name']).lower()
                if existing_cleaned == cleaned_name:
                    logger.debug(f"Found fuzzy match: {artist_name} -> {existing_artist['name']}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking artist existence: {e}")
            return False
    
    async def _video_exists_in_database(self, deps: PipelineDependencies, video_url: str) -> bool:
        """
        Check if this specific video has already been processed.
        """
        try:
            video_id = self._extract_video_id(video_url)
            if not video_id:
                return False
                
            response = deps.supabase.table("artists").select("id").eq("discovery_video_id", video_id).execute()
            return len(response.data) > 0
            
        except Exception as e:
            logger.error(f"Error checking video existence: {e}")
            return False
    
    def _validate_content(self, title: str, description: str) -> bool:
        """
        Validate content doesn't contain excluded keywords (AI, covers, etc.).
        """
        content = f"{title} {description or ''}".lower()
        
        for keyword in self.exclude_keywords:
            if keyword.lower() in content:
                logger.debug(f"Content rejected for keyword: {keyword}")
                return False
        
        return True
    
    def _extract_social_links_from_description(self, description: str) -> Dict[str, str]:
        """
        Extract social media links from video description.
        Now handles YouTube redirect URLs which wrap the actual social media links.
        
        Example redirect URL:
        https://www.youtube.com/redirect?event=video_description&redir_token=...&q=https%3A%2F%2Fwww.instagram.com%2Franirastacitimusic&v=...
        """
        if not description:
            return {}
        
        social_links = {}
        
        # First, extract URLs from YouTube redirect links
        redirect_pattern = r'https://www\.youtube\.com/redirect\?[^"\s<>]*?&q=([^&"\s<>]+)'
        redirect_matches = re.findall(redirect_pattern, description, re.IGNORECASE)
        
        # Decode the URLs from redirect parameters
        decoded_urls = []
        for encoded_url in redirect_matches:
            try:
                decoded_url = urllib.parse.unquote(encoded_url)
                decoded_urls.append(decoded_url)
                logger.debug(f"🔗 Decoded YouTube redirect: {encoded_url} -> {decoded_url}")
            except Exception as e:
                logger.debug(f"⚠️ Failed to decode redirect URL: {encoded_url}, error: {e}")
                continue
        
        # Also look for direct URLs in the description
        # Common URL pattern
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        direct_matches = re.findall(url_pattern, description, re.IGNORECASE)
        
        # Combine decoded redirect URLs and direct URLs
        all_urls = decoded_urls + direct_matches
        logger.debug(f"🔍 Found {len(all_urls)} total URLs: {len(decoded_urls)} from redirects, {len(direct_matches)} direct")
        
        # Enhanced patterns for social media platforms
        platform_patterns = {
            'instagram': [
                r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)',
                r'(?:https?://)?(?:www\.)?ig\.me/([a-zA-Z0-9._]+)',
                r'@([a-zA-Z0-9._]+)(?:\s|$)'  # Handle @username mentions
            ],
            'tiktok': [
                r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9._]+)',
                r'(?:https?://)?(?:vm\.)?tiktok\.com/([a-zA-Z0-9._]+)',
                r'(?:https?://)?(?:www\.)?tiktok\.com/t/([a-zA-Z0-9._]+)'
            ],
            'spotify': [
                r'(?:https?://)?(?:open\.)?spotify\.com/artist/([a-zA-Z0-9]+)',
                r'(?:https?://)?(?:open\.)?spotify\.com/user/([a-zA-Z0-9._]+)',
                r'(?:https?://)?(?:open\.)?spotify\.com/playlist/([a-zA-Z0-9]+)'
            ],
            'twitter': [
                r'(?:https?://)?(?:www\.)?twitter\.com/([a-zA-Z0-9_]+)',
                r'(?:https?://)?(?:www\.)?x\.com/([a-zA-Z0-9_]+)'
            ],
            'facebook': [
                r'(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9.]+)',
                r'(?:https?://)?(?:www\.)?fb\.com/([a-zA-Z0-9.]+)'
            ],
            'youtube': [
                r'(?:https?://)?(?:www\.)?youtube\.com/channel/([a-zA-Z0-9_-]+)',
                r'(?:https?://)?(?:www\.)?youtube\.com/c/([a-zA-Z0-9_-]+)',
                r'(?:https?://)?(?:www\.)?youtube\.com/@([a-zA-Z0-9_.-]+)',
                r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)'
            ],
            'website': [
                r'(?:https?://)?(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:/[^\s]*)?'
            ]
        }
        
        # Extract links for each platform
        for platform, patterns in platform_patterns.items():
            for pattern in patterns:
                # Check all URLs (both decoded redirects and direct)
                for url in all_urls:
                    matches = re.findall(pattern, url, re.IGNORECASE)
                    if matches:
                        # Take the first match and clean it
                        username_or_id = matches[0]
                        
                        # Construct the full URL
                        if platform == 'instagram':
                            if not username_or_id.startswith('@'):
                                full_url = f"https://www.instagram.com/{username_or_id}"
                            else:
                                full_url = f"https://www.instagram.com/{username_or_id[1:]}"
                        elif platform == 'tiktok':
                            if not username_or_id.startswith('@'):
                                full_url = f"https://www.tiktok.com/@{username_or_id}"
                            else:
                                full_url = f"https://www.tiktok.com/{username_or_id}"
                        elif platform == 'spotify':
                            full_url = f"https://open.spotify.com/artist/{username_or_id}"
                        elif platform == 'twitter':
                            full_url = f"https://twitter.com/{username_or_id}"
                        elif platform == 'facebook':
                            full_url = f"https://www.facebook.com/{username_or_id}"
                        elif platform == 'youtube':
                            if 'channel/' in url:
                                full_url = f"https://www.youtube.com/channel/{username_or_id}"
                            elif '@' in url:
                                full_url = f"https://www.youtube.com/@{username_or_id}"
                            else:
                                full_url = f"https://www.youtube.com/c/{username_or_id}"
                        elif platform == 'website':
                            full_url = url if url.startswith('http') else f"https://{url}"
                        else:
                            full_url = url
                        
                        # Only add if we don't already have this platform or if this is a better match
                        if platform not in social_links or len(full_url) > len(social_links[platform]):
                            social_links[platform] = full_url
                            logger.debug(f"✅ Found {platform}: {full_url}")
                            break  # Found a match for this platform, move to next platform
                
                # Also search in the raw description text for @mentions and direct patterns
                description_matches = re.findall(pattern, description, re.IGNORECASE)
                if description_matches and platform not in social_links:
                    username_or_id = description_matches[0]
                    if platform == 'instagram' and not username_or_id.startswith('@'):
                        full_url = f"https://www.instagram.com/{username_or_id}"
                        social_links[platform] = full_url
                        logger.debug(f"✅ Found {platform} from description: {full_url}")
        
        # Filter out invalid/generic links
        filtered_links = {}
        for platform, url in social_links.items():
            if self._is_valid_social_link(platform, url):
                filtered_links[platform] = url
            else:
                logger.debug(f"⚠️ Filtered out invalid {platform} link: {url}")
        
        logger.debug(f"🔗 Extracted {len(filtered_links)} valid social links: {list(filtered_links.keys())}")
        return filtered_links
    
    def _is_valid_social_link(self, platform: str, url: str) -> bool:
        """
        Validate that a social media link is legitimate and not generic/invalid.
        """
        if not url or len(url) < 10:
            return False
        
        # Platform-specific validation
        if platform == 'instagram':
            # Must have a username that's not too generic
            username_match = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', url)
            if username_match:
                username = username_match.group(1)
                # Filter out generic/invalid usernames
                invalid_usernames = ['home', 'explore', 'accounts', 'about', 'privacy', 'terms', 'help']
                return username not in invalid_usernames and len(username) >= 2
        
        elif platform == 'tiktok':
            # Must have a valid username format
            username_match = re.search(r'tiktok\.com/@([a-zA-Z0-9._]+)', url)
            if username_match:
                username = username_match.group(1)
                return len(username) >= 2
        
        elif platform == 'spotify':
            # Must have a valid artist/user ID
            return 'spotify.com/' in url and len(url) > 30
        
        elif platform == 'website':
            # Basic domain validation
            return '.' in url and not any(exclude in url.lower() for exclude in ['youtube.com', 'instagram.com', 'tiktok.com', 'spotify.com'])
        
        return True
    
    async def _extract_and_clean_artist_name(self, title: str) -> Optional[str]:
        """
        Extract and clean artist name using AI with regex fallback.
        """
        if not title:
            return None
        
        # First try AI cleaning
        if self.ai_cleaner and self.ai_cleaner.is_available():
            try:
                # Try AI extraction with original regex as baseline
                regex_result = self._extract_artist_name(title)
                cleaned_result = await self.ai_cleaner.clean_artist_name(title, regex_result)
                
                if cleaned_result and cleaned_result.confidence_score >= 0.7:
                    logger.info(f"🤖 AI cleaned artist: '{cleaned_result.artist_name}' (confidence: {cleaned_result.confidence_score:.2f})")
                    logger.debug(f"AI reasoning: {cleaned_result.reasoning}")
                    return cleaned_result.artist_name
                elif cleaned_result:
                    logger.warning(f"⚠️ Low confidence AI result: {cleaned_result.confidence_score:.2f}")
                    # Still use it but with warning
                    return cleaned_result.artist_name
                    
            except Exception as e:
                logger.warning(f"⚠️ AI artist extraction failed: {e}")
        
        # Fallback to regex method
        logger.info("🔄 Using regex fallback for artist extraction")
        return self._extract_artist_name(title)
    
    async def _clean_social_links(self, raw_links: Dict[str, str]) -> Optional[object]:
        """
        Clean and validate social media links using AI.
        """
        if not raw_links:
            return None
        
        # Try AI cleaning
        if self.ai_cleaner and self.ai_cleaner.is_available():
            try:
                cleaned_links = await self.ai_cleaner.clean_social_links(raw_links)
                if cleaned_links and cleaned_links.confidence_score >= 0.6:
                    logger.info(f"🔗 AI cleaned social links (confidence: {cleaned_links.confidence_score:.2f})")
                    return cleaned_links
                else:
                    logger.warning(f"⚠️ Low confidence social link cleaning")
                    
            except Exception as e:
                logger.warning(f"⚠️ AI social link cleaning failed: {e}")
        
        # Fallback: return raw links in expected format
        logger.info("🔄 Using raw social links without AI cleaning")
        
        # Create a simple object with the raw links
        class RawSocialLinks:
            def __init__(self, links):
                self.instagram = links.get('instagram')
                self.tiktok = links.get('tiktok')
                self.spotify = links.get('spotify')
                self.twitter = links.get('twitter')
                self.facebook = links.get('facebook')
                self.youtube = links.get('youtube')
                self.website = links.get('website')
        
        return RawSocialLinks(raw_links)
    
    async def _clean_channel_data(self, raw_data: Dict[str, Any]) -> Optional[object]:
        """
        Clean YouTube channel data using AI.
        """
        if not raw_data or not self.ai_cleaner or not self.ai_cleaner.is_available():
            return None
        
        try:
            cleaned_data = await self.ai_cleaner.clean_channel_data(raw_data)
            if cleaned_data and cleaned_data.confidence_score >= 0.6:
                logger.info(f"📺 AI cleaned channel data (confidence: {cleaned_data.confidence_score:.2f})")
                return cleaned_data
            else:
                logger.warning(f"⚠️ Low confidence channel data cleaning")
                return cleaned_data
                
        except Exception as e:
            logger.warning(f"⚠️ AI channel data cleaning failed: {e}")
            return None
    
    def _create_artist_profile(self, video_data: Dict[str, Any]) -> ArtistProfile:
        """
        Create initial artist profile from video data.
        """
        artist_name = video_data.get('extracted_artist_name', 'Unknown Artist')
        social_links = video_data.get('social_links', {})
        
        # Extract Spotify ID if available
        spotify_id = None
        spotify_url = social_links.get('spotify')
        if spotify_url:
            spotify_match = re.search(r'/artist/([a-zA-Z0-9]+)', spotify_url)
            if spotify_match:
                spotify_id = spotify_match.group(1)
        
        profile = ArtistProfile(
            id=uuid4(),
            name=artist_name,
            youtube_channel_id=video_data.get('channel_id'),
            youtube_channel_name=video_data.get('channel_title'),
            spotify_id=spotify_id,
            lyrical_themes=[],
            metadata={
                'discovery_video': {
                    'video_id': video_data.get('video_id'),
                    'title': video_data.get('title'),
                    'url': video_data.get('url'),
                    'published': video_data.get('published')
                },
                'social_links_from_description': social_links
            }
        )
        
        # Add social links
        for platform, url in social_links.items():
            profile.social_links[platform] = url
        
        logger.info(f"🎯 Created artist profile for {artist_name} with social links: {list(social_links.keys())}")
        if social_links:
            for platform, url in social_links.items():
                logger.info(f"   - {platform}: {url}")
        
        return profile
    
    async def _crawl_youtube_channel(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crawl YouTube channel for subscriber count and additional social links.
        Uses actual channel URL from video data if available.
        """
        try:
            # First priority: use actual channel URL if available
            channel_url = video_data.get('channel_url')
            
            if channel_url:
                logger.info(f"🎬 Using extracted channel URL: {channel_url}")
                channel_urls = [channel_url]  # Use the actual extracted URL
            else:
                # Fallback: construct URLs from channel info
                channel_name = video_data.get('channel_name') or video_data.get('channel_title')
                channel_id = video_data.get('channel_id')
                
                if not channel_name and not channel_id:
                    logger.warning("⚠️ No channel information available for crawling")
                    return {}
                
                # Skip if channel name is "Unknown" - but only if we also don't have video URL for fallback
                if channel_name == "Unknown" and not video_data.get('url'):
                    logger.warning(f"⚠️ Channel name is 'Unknown' and no video URL - skipping channel crawl for artist: {video_data.get('extracted_artist_name', 'N/A')}")
                    return {}
                elif channel_name == "Unknown":
                    logger.info(f"📺 Channel name unknown, but will try extracting from video URL for: {video_data.get('extracted_artist_name', 'N/A')}")
                
                # Build URLs based on available information
                channel_urls = []
                
                # If channel name is "Unknown", try to extract channel from video URL using crawl4ai_agent
                if channel_name == "Unknown" and video_data.get('url'):
                    try:
                        from app.agents.crawl4ai_agent import Crawl4AIAgent
                        crawl4ai_agent = Crawl4AIAgent()
                        extracted_channel = await crawl4ai_agent.extract_channel_from_video(video_data['url'])
                        if extracted_channel:
                            logger.info(f"✅ Extracted channel URL from video: {extracted_channel}")
                            channel_urls = [extracted_channel]
                            channel_url = extracted_channel
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to extract channel from video URL: {e}")
                
                if channel_id:
                    if channel_id.startswith('@'):
                        channel_urls.append(f"https://www.youtube.com/{channel_id}")
                    elif len(channel_id) == 24:  # YouTube channel ID format
                        channel_urls.append(f"https://www.youtube.com/channel/{channel_id}")
                    else:
                        channel_urls.extend([
                            f"https://www.youtube.com/c/{channel_id}",
                            f"https://www.youtube.com/user/{channel_id}"
                        ])
                
                if channel_name:
                    channel_urls.extend([
                        f"https://www.youtube.com/@{channel_name}",
                        f"https://www.youtube.com/c/{channel_name}",
                        f"https://www.youtube.com/user/{channel_name}"
                    ])
                
                # Remove duplicates while preserving order
                channel_urls = list(dict.fromkeys(channel_urls))
            
            logger.info(f"🎬 Crawling YouTube channel: {channel_name}")
            
            # Use Crawl4AI to scrape channel data
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
            from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
            
            browser_config = BrowserConfig(
                headless=True,
                viewport_width=1920,
                viewport_height=1080
            )
            
            # Enhanced schema for YouTube channel extraction
            schema = {
                "name": "YouTube Channel",
                "baseSelector": "body",  # Add required baseSelector
                "fields": [
                    {
                        "name": "subscriber_count_text",
                        "selector": "[data-testid='subscriber-count'], .subscriber-count, #subscriber-count, .yt-subscription-button-subscriber-count-branded-horizontal, .style-scope.ytd-c4-tabbed-header-renderer",
                        "type": "text"
                    },
                    {
                        "name": "channel_description",
                        "selector": "[data-testid='channel-description'], .channel-description, .about-description, .yt-formatted-string",
                        "type": "text"
                    },
                    {
                        "name": "verified_badge",
                        "selector": "[data-testid='verified-badge'], .verified-badge, .yt-icon-badge",
                        "type": "text"
                    },
                    {
                        "name": "social_links",
                        "selector": "a[href*='instagram.com'], a[href*='twitter.com'], a[href*='tiktok.com'], a[href*='spotify.com'], a[href*='facebook.com']",
                        "type": "list",
                        "attribute": "href"
                    }
                ]
            }
            
            extraction_strategy = JsonCssExtractionStrategy(schema)
            
            crawler_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                extraction_strategy=extraction_strategy,
                wait_until="domcontentloaded",
                page_timeout=30000,  # 30 second timeout
                delay_before_return_html=3.0,
                scan_full_page=True,  # Use built-in scrolling
                scroll_delay=0.5,
                verbose=True
            )
            
            # Try each URL format until one works
            for channel_url in channel_urls:
                try:
                    logger.info(f"Trying channel URL: {channel_url}")
                    
                    async with AsyncWebCrawler(config=browser_config) as crawler:
                        result = await crawler.arun(
                            url=channel_url,
                            config=crawler_config
                        )
                        
                        if result.success and result.html:
                            # Process extracted data
                            channel_data = {
                                'subscriber_count': 0,
                                'channel_url': channel_url,
                                'channel_description': '',
                                'social_links_from_channel': {},
                                'verified': False
                            }
                            
                            # Parse structured extraction
                            if result.extracted_content:
                                try:
                                    import json
                                    extracted = json.loads(result.extracted_content)
                                    
                                    # Handle case where extracted content is a list (take first item)
                                    if isinstance(extracted, list):
                                        if extracted:
                                            extracted = extracted[0]
                                        else:
                                            extracted = {}
                                    
                                    # Ensure extracted is a dictionary
                                    if isinstance(extracted, dict):
                                        # Extract subscriber count
                                        if extracted.get('subscriber_count_text'):
                                            channel_data['subscriber_count'] = self._parse_subscriber_count(extracted['subscriber_count_text'])
                                        
                                        # Extract description
                                        if extracted.get('channel_description'):
                                            channel_data['channel_description'] = extracted['channel_description'][:500]
                                        
                                        # Extract social links
                                        if extracted.get('social_links'):
                                            social_links = self._extract_social_links_from_channel_links(extracted['social_links'])
                                            channel_data['social_links_from_channel'] = social_links
                                        
                                        # Check verification
                                        if extracted.get('verified_badge'):
                                            channel_data['verified'] = True
                                    else:
                                        logger.debug(f"Extracted content is not a dictionary: {type(extracted)}")
                                        
                                except (json.JSONDecodeError, Exception) as e:
                                    logger.debug(f"Error parsing extracted content: {e}")
                            
                            # Fallback: use regex patterns on HTML
                            if channel_data['subscriber_count'] == 0:
                                channel_data['subscriber_count'] = self._extract_subscriber_count_from_html(result.html)
                            
                            if not channel_data['social_links_from_channel']:
                                channel_data['social_links_from_channel'] = self._extract_social_links_from_html(result.html)
                            
                            if channel_data['subscriber_count'] > 0 or channel_data['social_links_from_channel']:
                                # Clean channel data using AI
                                cleaned_data = await self._clean_channel_data(channel_data)
                                if cleaned_data:
                                    channel_data.update({
                                        'channel_name': cleaned_data.channel_name,
                                        'subscriber_count': cleaned_data.subscriber_count,
                                        'channel_description': cleaned_data.channel_description,
                                        'verified': cleaned_data.is_verified,
                                        'ai_confidence': cleaned_data.confidence_score,
                                        'cleaning_notes': cleaned_data.cleaning_notes
                                    })
                                    logger.info(f"✅ AI cleaned channel data: {cleaned_data.channel_name} ({cleaned_data.subscriber_count:,} subscribers, confidence: {cleaned_data.confidence_score:.2f})")
                                else:
                                    logger.info(f"✅ Successfully crawled YouTube channel: {channel_data['subscriber_count']:,} subscribers, {len(channel_data['social_links_from_channel'])} social links")
                                return channel_data
                            
                except Exception as e:
                    logger.debug(f"Failed to crawl {channel_url}: {e}")
                    continue
            
            logger.warning(f"⚠️ Could not crawl any YouTube channel URLs for: {channel_name}")
            return {
                'subscriber_count': 0,
                'channel_url': '',
                'channel_description': '',
                'social_links_from_channel': {},
                'verified': False
            }
            
        except Exception as e:
            logger.error(f"❌ YouTube channel crawling error: {e}")
            return {}
    
    async def _get_full_video_description(self, video_url: str) -> Optional[Dict[str, Any]]:
        """
        Crawl individual YouTube video page to get full description and metadata.
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Dict with video data including full description
        """
        try:
            logger.debug(f"🎬 Crawling full video data: {video_url}")
            
            from app.agents.crawl4ai_agent import Crawl4AIAgent
            
            # Initialize crawl4ai agent
            crawl_agent = Crawl4AIAgent()
            
            # Extract video data using enhanced extractors
            try:
                from enhanced_extractors import EnhancedYouTubeExtractor
                
                # Get the HTML content
                result = await crawl_agent.crawl_url(video_url)
                if not result or not result.get('success'):
                    logger.debug(f"⚠️ Failed to crawl video page: {video_url}")
                    return None
                
                html_content = result.get('html', '')
                if not html_content:
                    logger.debug(f"⚠️ No HTML content from video page: {video_url}")
                    return None
                
                # Extract video data using enhanced extractor
                video_data = EnhancedYouTubeExtractor.extract_video_data(html_content)
                
                if video_data and video_data.get('description'):
                    logger.debug(f"✅ Successfully extracted full video data ({len(video_data['description'])} chars description)")
                    return video_data
                else:
                    logger.debug(f"⚠️ No description found in video data")
                    return None
                    
            except ImportError:
                logger.debug("⚠️ Enhanced extractors not available, using basic crawling")
                # Fallback to basic crawling
                result = await crawl_agent.crawl_url(video_url)
                if result and result.get('success'):
                    # Try to extract description from HTML
                    html_content = result.get('html', '')
                    if html_content:
                        # Basic regex extraction for description
                        import re
                        desc_patterns = [
                            r'"description":{"simpleText":"([^"]+)"',
                            r'"description":"([^"]+)"',
                            r'<meta name="description" content="([^"]+)"',
                            r'<meta property="og:description" content="([^"]+)"'
                        ]
                        
                        for pattern in desc_patterns:
                            match = re.search(pattern, html_content)
                            if match:
                                description = match.group(1)
                                if len(description) > 50:  # Ensure we got substantial content
                                    return {'description': description}
                
                return None
                
        except Exception as e:
            logger.debug(f"⚠️ Error crawling full video description: {e}")
            return None
    
    async def _get_spotify_api_data(self, artist_name: str) -> Dict[str, Any]:
        """
        Get additional data from official Spotify API including avatar and genres.
        """
        try:
            logger.info(f"Getting Spotify API data for: {artist_name}")
            
            # Use the dedicated Spotify client
            from app.clients.spotify_client import get_spotify_client
            
            spotify_client = get_spotify_client()
            enriched_data = await spotify_client.get_enriched_artist_data(artist_name)
            
            if not enriched_data:
                logger.info(f"No artist found on Spotify for: {artist_name}")
                return {}
            
            # Convert to the expected format
            spotify_data = {
                'spotify_id': enriched_data.get('spotify_id'),
                'spotify_url': enriched_data.get('external_urls', {}).get('spotify'),
                'avatar_url': enriched_data.get('avatar_url'),
                'genres': enriched_data.get('genres', []),
                'followers': enriched_data.get('followers', 0),
                'popularity': enriched_data.get('popularity', 0),
                'name_match': enriched_data.get('name', '').lower() == artist_name.lower(),
                'top_tracks': enriched_data.get('top_tracks', [])
            }
            
            logger.info(f"✅ Retrieved Spotify API data for {artist_name}: {spotify_data['followers']:,} followers, {len(spotify_data['genres'])} genres")
            return spotify_data
            
        except Exception as e:
            logger.error(f"Error getting Spotify API data: {e}")
            return {}
    
    def _calculate_discovery_score(
        self,
        youtube_data: Dict[str, Any],
        enriched_data: Any,
        spotify_api_data: Dict[str, Any]
    ) -> int:
        """
        Calculate sophisticated discovery score (0-100) representing artist's career progression.
        
        Score components:
        - YouTube: 25 points (subscribers, engagement)
        - Spotify: 25 points (monthly listeners, popularity) 
        - Instagram: 20 points (followers, engagement rate)
        - TikTok: 15 points (followers, likes ratio)
        - Growth Trajectory: 10 points (growth patterns, potential)
        - Artificial Inflation Detection: -20 points penalty
        
        Score ranges:
        - 0-20: Emerging talent (just starting)
        - 21-40: Developing artist (building audience)
        - 41-60: Growing artist (steady momentum) 
        - 61-80: Established indie artist (strong following)
        - 81-100: Viral/breakthrough potential (high momentum)
        """
        score = 0
        
        try:
            # Extract metrics safely
            spotify_listeners = 0
            instagram_followers = 0
            tiktok_followers = 0
            tiktok_likes = 0
            
            # Handle different enriched_data structures
            if hasattr(enriched_data, 'profile'):
                if hasattr(enriched_data.profile, 'follower_counts'):
                    spotify_listeners = enriched_data.profile.follower_counts.get('spotify_monthly_listeners', 0) or 0
                    instagram_followers = enriched_data.profile.follower_counts.get('instagram', 0) or 0
                    tiktok_followers = enriched_data.profile.follower_counts.get('tiktok', 0) or 0
                
                if hasattr(enriched_data.profile, 'metadata'):
                    tiktok_likes = enriched_data.profile.metadata.get('tiktok_likes', 0) or 0
            
            youtube_subscribers = youtube_data.get('subscriber_count', 0) or 0
            
            # Spotify API data (takes precedence over scraped data)
            if spotify_api_data:
                api_followers = spotify_api_data.get('followers', 0)
                if api_followers > spotify_listeners:
                    spotify_listeners = api_followers
            
            # YouTube scoring (25 points max) - Lower thresholds for undiscovered talent
            youtube_score = 0
            if youtube_subscribers >= 50000:
                youtube_score = 25  # Max score for this range
            elif youtube_subscribers >= 25000:
                youtube_score = 22
            elif youtube_subscribers >= 10000:
                youtube_score = 18
            elif youtube_subscribers >= 5000:
                youtube_score = 15
            elif youtube_subscribers >= 1000:
                youtube_score = 12
            elif youtube_subscribers >= 500:
                youtube_score = 8
            elif youtube_subscribers >= 100:
                youtube_score = 5
            elif youtube_subscribers >= 50:
                youtube_score = 3
            elif youtube_subscribers > 0:
                youtube_score = 1
            
            score += youtube_score
            
            # Spotify scoring (25 points max) - Adjusted for monthly listeners
            spotify_score = 0
            if spotify_listeners >= 100000:
                spotify_score = 25
            elif spotify_listeners >= 50000:
                spotify_score = 22
            elif spotify_listeners >= 25000:
                spotify_score = 18
            elif spotify_listeners >= 10000:
                spotify_score = 15
            elif spotify_listeners >= 5000:
                spotify_score = 12
            elif spotify_listeners >= 1000:
                spotify_score = 8
            elif spotify_listeners >= 500:
                spotify_score = 5
            elif spotify_listeners >= 100:
                spotify_score = 3
            elif spotify_listeners > 0:
                spotify_score = 1
            
            score += spotify_score
            
            # Instagram scoring (20 points max)
            instagram_score = 0
            if instagram_followers >= 100000:
                instagram_score = 20
            elif instagram_followers >= 50000:
                instagram_score = 17
            elif instagram_followers >= 25000:
                instagram_score = 14
            elif instagram_followers >= 10000:
                instagram_score = 12
            elif instagram_followers >= 5000:
                instagram_score = 9
            elif instagram_followers >= 1000:
                instagram_score = 6
            elif instagram_followers >= 500:
                instagram_score = 4
            elif instagram_followers >= 100:
                instagram_score = 2
            elif instagram_followers > 0:
                instagram_score = 1
            
            score += instagram_score
            
            # TikTok scoring (15 points max) - Includes engagement factor
            tiktok_score = 0
            if tiktok_followers >= 100000:
                tiktok_score = 15
            elif tiktok_followers >= 50000:
                tiktok_score = 13
            elif tiktok_followers >= 25000:
                tiktok_score = 11
            elif tiktok_followers >= 10000:
                tiktok_score = 9
            elif tiktok_followers >= 5000:
                tiktok_score = 7
            elif tiktok_followers >= 1000:
                tiktok_score = 5
            elif tiktok_followers >= 500:
                tiktok_score = 3
            elif tiktok_followers >= 100:
                tiktok_score = 2
            elif tiktok_followers > 0:
                tiktok_score = 1
            
            # TikTok engagement bonus
            if tiktok_followers > 0 and tiktok_likes > 0:
                likes_per_follower = tiktok_likes / tiktok_followers
                if likes_per_follower > 10:  # High engagement
                    tiktok_score = min(tiktok_score + 2, 15)
                elif likes_per_follower > 5:  # Good engagement
                    tiktok_score = min(tiktok_score + 1, 15)
            
            score += tiktok_score
            
            # Growth trajectory and potential (10 points max)
            growth_score = 0
            
            # Multi-platform presence bonus
            platforms_with_following = sum([
                1 if youtube_subscribers > 0 else 0,
                1 if spotify_listeners > 0 else 0,
                1 if instagram_followers > 0 else 0,
                1 if tiktok_followers > 0 else 0
            ])
            
            if platforms_with_following >= 4:
                growth_score += 4
            elif platforms_with_following >= 3:
                growth_score += 3
            elif platforms_with_following >= 2:
                growth_score += 2
            elif platforms_with_following >= 1:
                growth_score += 1
            
            # Content quality indicators
            if hasattr(enriched_data, 'profile') and hasattr(enriched_data.profile, 'metadata'):
                if enriched_data.profile.metadata.get('top_tracks'):
                    growth_score += 2  # Has released music
                if enriched_data.profile.metadata.get('lyrics_themes'):
                    growth_score += 2  # Quality lyrical content
            
            # Spotify popularity bonus (from API)
            if spotify_api_data.get('popularity', 0) > 30:
                growth_score += 2
            
            score += min(growth_score, 10)
            
            # Artificial inflation detection (-20 points max penalty)
            artificial_inflation_penalty = self._detect_artificial_inflation(
                spotify_listeners, instagram_followers, tiktok_followers, youtube_subscribers
            )
            score -= artificial_inflation_penalty
            
            # Undiscovered talent bonus (5 points) - Artists with good content but low overall reach
            if score < 30 and platforms_with_following >= 2:
                score += 5  # Bonus for multi-platform emerging artists
            
            final_score = max(0, min(score, 100))  # Clamp between 0 and 100
            
            logger.info(f"📊 Discovery Score Breakdown:")
            logger.info(f"   YouTube ({youtube_subscribers:,} subs): {youtube_score}/25")
            logger.info(f"   Spotify ({spotify_listeners:,} listeners): {spotify_score}/25") 
            logger.info(f"   Instagram ({instagram_followers:,} followers): {instagram_score}/20")
            logger.info(f"   TikTok ({tiktok_followers:,} followers): {tiktok_score}/15")
            logger.info(f"   Growth/Quality: {min(growth_score, 10)}/10")
            logger.info(f"   Inflation Penalty: -{artificial_inflation_penalty}")
            logger.info(f"   🎯 FINAL SCORE: {final_score}/100")
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating discovery score: {e}")
            return 0
    
    def _detect_artificial_inflation(
        self,
        spotify_listeners: int,
        instagram_followers: int,
        tiktok_followers: int,
        youtube_subscribers: int
    ) -> int:
        """
        Detect artificial inflation and return penalty points.
        """
        penalty = 0
        
        try:
            # Get all valid metrics
            metrics = [m for m in [spotify_listeners, instagram_followers, tiktok_followers, youtube_subscribers] if m > 0]
            
            if len(metrics) < 2:
                return 0  # Not enough data to compare
            
            # Find max and min metrics
            max_metric = max(metrics)
            min_metric = min(metrics)
            
            if min_metric == 0:
                return 0
            
            # Calculate ratio between highest and lowest
            ratio = max_metric / min_metric
            
            # Suspicious patterns
            if ratio > 1000:  # One platform has 1000x more followers
                penalty += 15
                logger.warning(f"Very high follower ratio detected: {ratio:.1f}")
            elif ratio > 100:  # One platform has 100x more followers
                penalty += 10
                logger.warning(f"High follower ratio detected: {ratio:.1f}")
            elif ratio > 50:  # One platform has 50x more followers
                penalty += 5
                logger.warning(f"Moderate follower ratio detected: {ratio:.1f}")
            
            # Specific suspicious patterns
            if spotify_listeners > 1000000 and max(instagram_followers, tiktok_followers) < 50000:
                penalty += 10
                logger.warning(f"High Spotify listeners ({spotify_listeners:,}) but low social media presence")
            
            if instagram_followers > 100000 and spotify_listeners < 1000:
                penalty += 5
                logger.warning(f"High Instagram followers ({instagram_followers:,}) but very low Spotify listeners")
            
            return min(penalty, 20)  # Cap penalty at 20 points
            
        except Exception as e:
            logger.error(f"Error detecting artificial inflation: {e}")
            return 0
    
    async def _store_artist_in_database(
        self,
        deps: PipelineDependencies,
        artist_profile: ArtistProfile,
        enriched_data: Any,
        youtube_data: Dict[str, Any],
        spotify_api_data: Dict[str, Any],
        discovery_score: int,
        lyrical_analysis: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Store complete artist data in Supabase database.
        """
        try:
            # Prepare artist data for database
            artist_data = {
                'name': artist_profile.name,
                'youtube_channel_id': artist_profile.youtube_channel_id,
                'youtube_subscriber_count': youtube_data.get('subscriber_count', 0),
                'youtube_channel_url': youtube_data.get('channel_url', ''),
                'spotify_id': artist_profile.spotify_id,
                'spotify_url': artist_profile.social_links.get('spotify'),
                # Spotify data
                'spotify_monthly_listeners': enriched_data.profile.follower_counts.get('spotify_monthly_listeners', 0) or 0,
                'spotify_top_city': enriched_data.profile.metadata.get('spotify_top_city', ''),
                'spotify_biography': enriched_data.profile.bio or '',
                'spotify_genres': enriched_data.profile.genres or [],
                # Instagram data  
                'instagram_url': enriched_data.profile.social_links.get('instagram') or artist_profile.social_links.get('instagram'),
                'instagram_follower_count': enriched_data.profile.follower_counts.get('instagram', 0) or 0,
                # TikTok data
                'tiktok_url': enriched_data.profile.social_links.get('tiktok') or artist_profile.social_links.get('tiktok'),
                'tiktok_follower_count': enriched_data.profile.follower_counts.get('tiktok', 0) or 0,
                'tiktok_likes_count': enriched_data.profile.metadata.get('tiktok_likes', 0) or 0,
                # Other social media
                'twitter_url': enriched_data.profile.social_links.get('twitter') or artist_profile.social_links.get('twitter'),
                'facebook_url': enriched_data.profile.social_links.get('facebook') or artist_profile.social_links.get('facebook'),
                'website_url': enriched_data.profile.social_links.get('website') or artist_profile.social_links.get('website'),
                # Music analysis
                'music_theme_analysis': lyrical_analysis or enriched_data.profile.metadata.get('lyrics_themes', ''),
                # Spotify API data
                'avatar_url': spotify_api_data.get('avatar_url'),
                'spotify_popularity_score': spotify_api_data.get('popularity', 0),
                'spotify_followers': spotify_api_data.get('followers', 0),
                # Discovery metadata
                'discovery_source': 'youtube',
                'discovery_video_id': artist_profile.metadata.get('discovery_video', {}).get('video_id'),
                'discovery_video_title': artist_profile.metadata.get('discovery_video', {}).get('title'),
                'discovery_score': discovery_score,
                'last_crawled_at': datetime.utcnow().isoformat(),
                'is_validated': True
            }
            
            # Insert into database
            response = deps.supabase.table("artists").insert(artist_data).execute()
            
            if response.data:
                artist_record = response.data[0]
                logger.info(f"✅ Stored artist in database: {artist_profile.name} (ID: {artist_record['id']})")
                return artist_record
            else:
                logger.error(f"❌ Failed to store artist in database: {artist_profile.name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error storing artist in database: {e}")
            return None
    
    def _create_empty_result(self, message: str, start_time: float) -> Dict[str, Any]:
        """
        Create empty result structure.
        """
        return {
            'status': 'success',
            'message': message,
            'data': {
                'artists': [],
                'total_processed': 0,
                'total_found': 0,
                'execution_time': time.time() - start_time,
                'discovery_metadata': {}
            }
        }
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        try:
            if 'watch?v=' in url:
                return url.split('watch?v=')[1].split('&')[0]
            return None
        except:
            return None
    
    def _validate_title_contains_search_terms(self, title: str) -> bool:
        """
        Validate if the title appears to be a legitimate music video (less restrictive).
        """
        if not title:
            return False
            
        title_lower = title.lower()
        
        # Primary high-quality indicators
        high_quality_terms = [
            "official music video",
            "official video", 
            "official mv",
            "official audio",
            "official lyric video",
            "official visualizer"
        ]
        
        for term in high_quality_terms:
            if term in title_lower:
                return True
        
        # Secondary indicators - look for music video structure
        import re
        music_patterns = [
            r'\w+\s*-\s*\w+',  # Artist - Song format
            r'\w+\s*\|\s*\w+',  # Artist | Song format  
            r'\w+:\s*\w+',      # Artist: Song format
        ]
        
        has_music_structure = False
        for pattern in music_patterns:
            if re.search(pattern, title_lower):
                has_music_structure = True
                break
        
        if has_music_structure:
            # More flexible secondary terms
            secondary_terms = [
                "music video",
                "mv",
                "video",
                "lyric video", 
                "lyrics",
                "visualizer",
                "performance",
                "live"
            ]
            
            for term in secondary_terms:
                if term in title_lower:
                    return True
            
            # Even if no explicit "video" term, accept if it has proper music structure
            # and doesn't contain obvious negative indicators
            negative_indicators = [
                "cover", "remix by", "reaction", "tutorial", 
                "how to", "instrumental", "karaoke", "mashup"
            ]
            
            has_negative = any(neg in title_lower for neg in negative_indicators)
            if not has_negative:
                return True
        
        return False
    
    def _parse_subscriber_count(self, text: str) -> int:
        """Parse subscriber count from text with K, M, B suffixes."""
        try:
            if not text:
                return 0
            
            # Remove common words and clean text
            text = text.lower().replace('subscribers', '').replace('subscriber', '').strip()
            
            # Handle K, M, B suffixes
            multipliers = {'k': 1000, 'm': 1000000, 'b': 1000000000}
            
            for suffix, multiplier in multipliers.items():
                if suffix in text:
                    number = float(text.replace(suffix, '').replace(',', '').strip())
                    return int(number * multiplier)
            
            # Try to parse as regular number
            clean_number = re.sub(r'[^\d.]', '', text)
            if clean_number:
                return int(float(clean_number))
            
            return 0
        except:
            return 0
    
    def _extract_subscriber_count_from_html(self, html: str) -> int:
        """Extract subscriber count using regex patterns."""
        patterns = [
            r'(\d+(?:\.\d+)?[KMB]?)\s*subscribers?',
            r'"subscriberCountText":\{"runs":\[\{"text":"([^"]+)"\}',
            r'"subscriberCount":(\d+)',
            r'subscribers?["\s]*:\s*["\s]*(\d+(?:\.\d+)?[KMB]?)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                for match in matches:
                    parsed = self._parse_subscriber_count(match)
                    if parsed > 0:
                        return parsed
        return 0
    
    def _extract_social_links_from_channel_links(self, links: List[str]) -> Dict[str, str]:
        """Extract social media links from channel description."""
        social_links = {}
        
        for link in links:
            if 'instagram.com' in link:
                social_links['instagram'] = link
            elif 'twitter.com' in link or 'x.com' in link:
                social_links['twitter'] = link
            elif 'tiktok.com' in link:
                social_links['tiktok'] = link
            elif 'spotify.com' in link:
                social_links['spotify'] = link
            elif 'facebook.com' in link:
                social_links['facebook'] = link
        
        return social_links
    
    def _extract_social_links_from_html(self, html: str) -> Dict[str, str]:
        """Extract social media links using regex patterns."""
        social_links = {}
        
        # Enhanced patterns for social media links
        link_patterns = {
            'instagram': [
                r'href="(https?://(?:www\.)?instagram\.com/[^"]+)"',
                r'"(https?://(?:www\.)?instagram\.com/[^"]+)"',
            ],
            'twitter': [
                r'href="(https?://(?:www\.)?(?:twitter|x)\.com/[^"]+)"',
                r'"(https?://(?:www\.)?(?:twitter|x)\.com/[^"]+)"',
            ],
            'tiktok': [
                r'href="(https?://(?:www\.)?tiktok\.com/[^"]+)"',
                r'"(https?://(?:www\.)?tiktok\.com/[^"]+)"',
            ],
            'spotify': [
                r'href="(https?://open\.spotify\.com/artist/[^"]+)"',
                r'"(https?://open\.spotify\.com/artist/[^"]+)"',
            ],
            'facebook': [
                r'href="(https?://(?:www\.)?facebook\.com/[^"]+)"',
                r'"(https?://(?:www\.)?facebook\.com/[^"]+)"',
            ]
        }
        
        for platform, patterns in link_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    # Take the first valid match
                    social_links[platform] = matches[0]
                    break
        
        return social_links
    
    async def _extract_social_from_channel(self, channel_url: str) -> Dict[str, str]:
        """
        Extract social media links from YouTube channel About page as fallback.
        
        Args:
            channel_url: YouTube channel URL
            
        Returns:
            Dictionary of social media links found on channel
        """
        if not channel_url:
            return {}
        
        logger.info(f"🔍 Extracting social links from channel: {channel_url}")
        
        try:
            # Use Crawl4AI to scrape the channel's About page
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
            
            browser_config = BrowserConfig(
                headless=True,
                browser_type="chromium",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Build the About page URL
            about_url = channel_url.rstrip('/') + '/about'
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                config = CrawlerRunConfig(
                    word_count_threshold=10,
                    extraction_strategy=None,  # Just get raw content
                    css_selector=None,
                    screenshot=False,
                    pdf=False,
                    verbose=False
                )
                
                result = await crawler.arun(
                    url=about_url,
                    config=config,
                    session_id=f"channel_social_{hash(channel_url)}"
                )
                
                if not result.success:
                    logger.warning(f"⚠️ Failed to crawl channel About page: {about_url}")
                    return {}
                
                # Extract social links from the HTML content
                social_links = self._extract_social_links_from_channel_html(result.html)
                
                if social_links:
                    logger.info(f"✅ Found {len(social_links)} social links from channel About page")
                    return social_links
                else:
                    logger.debug(f"No social links found in channel About page")
                    return {}
                    
        except Exception as e:
            logger.error(f"❌ Error extracting social links from channel {channel_url}: {e}")
            return {}
    
    def _extract_social_links_from_channel_html(self, html: str) -> Dict[str, str]:
        """
        Extract social media links from YouTube channel About page HTML.
        
        Args:
            html: HTML content from channel About page
            
        Returns:
            Dictionary of extracted social media links
        """
        if not html:
            return {}
        
        links = {}
        
        # Instagram patterns - look for various formats in channel HTML
        instagram_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?',
            r'"instagram"[^"]*"([^"]*instagram\.com/[a-zA-Z0-9_.]+)"',
            r'instagram\.com/([a-zA-Z0-9_.]+)',
        ]
        
        for pattern in instagram_patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                if 'instagram' not in links:
                    if match.groups():
                        username = match.group(1)
                        if len(username) > 1 and '.' not in username[-3:]:  # Basic validation
                            links['instagram'] = f"https://instagram.com/{username}"
                            break
                    else:
                        # Full URL captured
                        full_url = match.group(0)
                        if 'instagram.com/' in full_url:
                            links['instagram'] = full_url if full_url.startswith('http') else f"https://{full_url}"
                            break
        
        # TikTok patterns
        tiktok_patterns = [
            r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]+)/?',
            r'"tiktok"[^"]*"([^"]*tiktok\.com/@[a-zA-Z0-9_.]+)"',
            r'tiktok\.com/@([a-zA-Z0-9_.]+)',
        ]
        
        for pattern in tiktok_patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                if 'tiktok' not in links:
                    if match.groups():
                        username = match.group(1)
                        if len(username) > 1:
                            links['tiktok'] = f"https://tiktok.com/@{username}"
                            break
                    else:
                        full_url = match.group(0)
                        if 'tiktok.com/@' in full_url:
                            links['tiktok'] = full_url if full_url.startswith('http') else f"https://{full_url}"
                            break
        
        # Spotify patterns
        spotify_patterns = [
            r'(?:https?://)?open\.spotify\.com/artist/([a-zA-Z0-9]+)',
            r'"spotify"[^"]*"([^"]*spotify\.com/artist/[a-zA-Z0-9]+)"',
            r'spotify\.com/artist/([a-zA-Z0-9]+)',
        ]
        
        for pattern in spotify_patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                if 'spotify' not in links:
                    if match.groups():
                        artist_id = match.group(1)
                        if len(artist_id) == 22:  # Spotify artist ID length
                            links['spotify'] = f"https://open.spotify.com/artist/{artist_id}"
                            break
                    else:
                        full_url = match.group(0)
                        if 'spotify.com/artist/' in full_url:
                            links['spotify'] = full_url if full_url.startswith('http') else f"https://{full_url}"
                            break
        
        # Twitter/X patterns
        twitter_patterns = [
            r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)/?',
            r'"twitter"[^"]*"([^"]*(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+)"',
            r'(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)',
        ]
        
        for pattern in twitter_patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                if 'twitter' not in links:
                    if match.groups():
                        username = match.group(1)
                        if len(username) > 1 and username not in ['home', 'login', 'signup', 'explore']:
                            links['twitter'] = f"https://twitter.com/{username}"
                            break
                    else:
                        full_url = match.group(0)
                        if any(domain in full_url for domain in ['twitter.com/', 'x.com/']):
                            links['twitter'] = full_url if full_url.startswith('http') else f"https://{full_url}"
                            break
        
        # Facebook patterns
        facebook_patterns = [
            r'(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9_.]+)/?',
            r'"facebook"[^"]*"([^"]*facebook\.com/[a-zA-Z0-9_.]+)"',
            r'facebook\.com/([a-zA-Z0-9_.]+)',
        ]
        
        for pattern in facebook_patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                if 'facebook' not in links:
                    if match.groups():
                        page_name = match.group(1)
                        if len(page_name) > 1 and page_name not in ['login', 'home', 'pages']:
                            links['facebook'] = f"https://facebook.com/{page_name}"
                            break
                    else:
                        full_url = match.group(0)
                        if 'facebook.com/' in full_url:
                            links['facebook'] = full_url if full_url.startswith('http') else f"https://{full_url}"
                            break
        
        logger.debug(f"Extracted social links from channel HTML: {links}")
        return links
    
    def _validate_view_count(self, view_count: int) -> bool:
        """
        Validate that video has less than 50k views to find undiscovered talent.
        """
        try:
            if view_count is None:
                return True  # Allow if view count is unknown
            
            # Convert string view counts if needed
            if isinstance(view_count, str):
                # Handle formats like "1.2K", "45K", "1.5M"
                view_count = view_count.lower().replace(',', '')
                if 'k' in view_count:
                    view_count = float(view_count.replace('k', '')) * 1000
                elif 'm' in view_count:
                    view_count = float(view_count.replace('m', '')) * 1000000
                elif 'b' in view_count:
                    view_count = float(view_count.replace('b', '')) * 1000000000
                else:
                    view_count = float(view_count)
            
            is_valid = view_count < self.max_view_count
            if not is_valid:
                logger.debug(f"View count {view_count:,} exceeds limit of {self.max_view_count:,}")
            
            return is_valid
            
        except Exception as e:
            logger.warning(f"Error validating view count '{view_count}': {e}")
            return True  # Allow if parsing fails
    
    def _validate_english_language(self, text: str) -> bool:
        """
        Validate that text contains only English characters.
        """
        if not text:
            return False
        
        import re
        
        # Allow English letters, numbers, spaces, and common punctuation
        english_pattern = re.compile(r'^[a-zA-Z0-9\s\-\.\,\!\?\(\)\[\]\&\'\"]+$')
        
        # Check if text matches English pattern
        is_english = bool(english_pattern.match(text.strip()))
        
        if not is_english:
            logger.debug(f"Text '{text}' contains non-English characters")
        
        return is_english
    
    def _is_well_known_artist(self, artist_name: str) -> bool:
        """
        Check if artist name matches well-known artists (indicates covers/AI content).
        """
        if not artist_name:
            return False
        
        artist_lower = artist_name.lower().strip()
        
        # Check against well-known artists list
        for known_artist in self.well_known_artists:
            if known_artist in artist_lower:
                logger.debug(f"Artist '{artist_name}' matches well-known artist '{known_artist}'")
                return True
        
        return False
    
    async def _extract_lyrics_from_musixmatch(self, artist_name: str, song_titles: List[str]) -> Dict[str, str]:
        """
        Extract lyrics for the top 5 songs from Musixmatch.
        """
        lyrics_data = {}
        
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
            
            browser_config = BrowserConfig(
                headless=True,
                viewport_width=1920,
                viewport_height=1080
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                for song_item in song_titles[:5]:  # Top 5 songs only
                    try:
                        # Extract song title from dictionary or use as string
                        if isinstance(song_item, dict):
                            song_title = song_item.get('name', str(song_item))
                        else:
                            song_title = str(song_item)
                        
                        # Clean song title for URL
                        clean_artist = artist_name.replace(' ', '-').replace('&', 'and')
                        clean_song = song_title.replace(' ', '-').replace('&', 'and')
                        
                        # Build Musixmatch URL
                        musixmatch_url = f"https://www.musixmatch.com/lyrics/{clean_artist}/{clean_song}"
                        
                        config = CrawlerRunConfig(
                            css_selector='.lyrics__content__ok, .mxm-lyrics__content',
                            word_count_threshold=50,
                            extraction_strategy=None,
                            wait_until="domcontentloaded",
                            page_timeout=15000,
                            delay_before_return_html=2.0,
                            screenshot=False,
                            pdf=False,
                            verbose=False
                        )
                        
                        result = await crawler.arun(
                            url=musixmatch_url,
                            config=config,
                            session_id=f"musixmatch_{hash(artist_name + song_title)}"
                        )
                        
                        if result.success and result.markdown:
                            # Extract lyrics from markdown
                            lyrics_text = self._clean_lyrics_text(result.markdown)
                            if lyrics_text and len(lyrics_text) > 50:
                                lyrics_data[song_title] = lyrics_text
                                logger.info(f"✅ Extracted lyrics for '{song_title}' by {artist_name}")
                            else:
                                logger.warning(f"⚠️ No valid lyrics found for '{song_title}'")
                        else:
                            logger.warning(f"⚠️ Failed to scrape lyrics for '{song_title}': {result.error_message if hasattr(result, 'error_message') else 'Unknown error'}")
                    
                    except Exception as e:
                        logger.error(f"Error extracting lyrics for '{song_title}': {e}")
                        continue
                    
                    # Rate limiting
                    await asyncio.sleep(1.0)
            
            logger.info(f"📝 Extracted lyrics for {len(lyrics_data)} songs by {artist_name}")
            return lyrics_data
            
        except Exception as e:
            logger.error(f"Error extracting lyrics from Musixmatch: {e}")
            return {}
    
    def _clean_lyrics_text(self, raw_text: str) -> str:
        """
        Clean and format lyrics text extracted from Musixmatch.
        """
        if not raw_text:
            return ""
        
        import re
        
        # Remove common Musixmatch elements
        cleaned = re.sub(r'Musixmatch.*?lyrics', '', raw_text, flags=re.IGNORECASE)
        cleaned = re.sub(r'You might also like.*?\n', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[.*?\]', '', cleaned)  # Remove annotations like [Verse 1]
        cleaned = re.sub(r'\(.*?\)', '', cleaned)  # Remove parenthetical notes
        
        # Clean up whitespace
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    async def _analyze_lyrics_with_deepseek(self, lyrics_data: Dict[str, str], artist_name: str) -> str:
        """
        Analyze lyrics using DeepSeek to extract recurring themes and sentiment.
        """
        try:
            if not lyrics_data:
                return ""
            
            # Combine all lyrics
            all_lyrics = "\n\n".join([f"Song: {title}\n{lyrics}" for title, lyrics in lyrics_data.items()])
            
            # Use existing AI cleaner if available
            if self.ai_cleaner and self.ai_cleaner.is_available():
                analysis_prompt = f"""
                Analyze the following lyrics from {artist_name} and provide a one-sentence theme analysis:
                
                {all_lyrics}
                
                Please identify the main recurring themes, emotions, and overall sentiment in ONE SENTENCE.
                Focus on: love, relationships, success, struggle, party, introspection, social issues, etc.
                """
                
                try:
                    # This would use the existing AI cleaner infrastructure
                    # For now, return a simple analysis based on keyword frequency
                    return self._simple_lyrics_analysis(all_lyrics)
                except Exception as e:
                    logger.warning(f"DeepSeek analysis failed: {e}")
                    return self._simple_lyrics_analysis(all_lyrics)
            else:
                return self._simple_lyrics_analysis(all_lyrics)
                
        except Exception as e:
            logger.error(f"Error analyzing lyrics with DeepSeek: {e}")
            return ""
    
    def _simple_lyrics_analysis(self, lyrics_text: str) -> str:
        """
        Simple keyword-based lyrics analysis as fallback.
        """
        if not lyrics_text:
            return ""
        
        lyrics_lower = lyrics_text.lower()
        
        # Theme keywords
        themes = {
            'love_relationships': ['love', 'heart', 'baby', 'girl', 'boy', 'kiss', 'romance', 'together'],
            'success_money': ['money', 'cash', 'rich', 'success', 'win', 'gold', 'diamond', 'fame'],
            'party_lifestyle': ['party', 'dance', 'club', 'night', 'drink', 'fun', 'celebrate'],
            'struggle_hardship': ['struggle', 'pain', 'hard', 'fight', 'difficult', 'broke', 'stress'],
            'introspective': ['think', 'feel', 'mind', 'soul', 'memory', 'dream', 'hope'],
            'social_issues': ['world', 'people', 'society', 'change', 'justice', 'freedom', 'peace']
        }
        
        theme_scores = {}
        for theme, keywords in themes.items():
            score = sum(lyrics_lower.count(keyword) for keyword in keywords)
            if score > 0:
                theme_scores[theme] = score
        
        if not theme_scores:
            return "Mixed themes and personal expression"
        
        # Get top theme
        top_theme = max(theme_scores, key=theme_scores.get)
        
        theme_descriptions = {
            'love_relationships': 'Focuses on love, relationships, and romantic connections',
            'success_money': 'Emphasizes success, wealth, and material achievement',
            'party_lifestyle': 'Centers around party culture, nightlife, and celebration',
            'struggle_hardship': 'Explores personal struggles, hardships, and overcoming challenges',
            'introspective': 'Reflects on personal thoughts, emotions, and inner experiences',
            'social_issues': 'Addresses social themes, community, and broader world issues'
        }
        
        return theme_descriptions.get(top_theme, "Mixed themes and personal expression")
 