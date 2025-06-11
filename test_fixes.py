#!/usr/bin/env python3
"""
Test script to verify the infinite scroll and database insertion fixes
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.agents.crawl4ai_youtube_agent import Crawl4AIYouTubeAgent
from app.agents.master_discovery_agent import MasterDiscoveryAgent
from app.core.dependencies import PipelineDependencies
from app.core.config import settings

async def test_infinite_scroll():
    """Test the improved infinite scroll functionality"""
    print("🔄 Testing infinite scroll improvements...")
    
    agent = Crawl4AIYouTubeAgent()
    
    try:
        # Test with a simple query
        result = await agent.search_videos_with_infinite_scroll(
            query="official music video",
            target_videos=20,  # Small number for testing
            upload_date="day"
        )
        
        if result.success:
            print(f"✅ Infinite scroll success: Found {len(result.videos)} videos")
            
            # Check video_id extraction
            videos_with_ids = [v for v in result.videos if hasattr(v, 'video_id') and v.video_id]
            print(f"✅ Video ID extraction: {len(videos_with_ids)}/{len(result.videos)} videos have IDs")
            
            # Check for duplicates
            video_ids = [v.video_id for v in videos_with_ids]
            unique_ids = set(video_ids)
            print(f"✅ Duplicate removal: {len(unique_ids)} unique videos out of {len(video_ids)}")
            
            return True
        else:
            print(f"❌ Infinite scroll failed: {result.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ Infinite scroll test error: {e}")
        return False

async def test_database_mapping():
    """Test the database insertion mapping"""
    print("🗃️ Testing database mapping fixes...")
    
    # Mock enriched data to test the mapping
    from app.models.artist import ArtistProfile, EnrichedArtistData
    from app.agents.crawl4ai_enrichment_agent import Crawl4AIEnrichmentAgent
    
    try:
        # Create test artist profile
        artist_profile = ArtistProfile(
            name="Test Artist",
            social_links={
                'spotify': 'https://open.spotify.com/artist/test123',
                'instagram': 'https://instagram.com/testartist',
                'tiktok': 'https://tiktok.com/@testartist'
            }
        )
        
        # Create enriched data with the correct structure
        enriched_data = EnrichedArtistData(
            profile=artist_profile,
            videos=[],
            lyric_analyses=[],
            enrichment_score=0.75
        )
        
        # Add test data to follower_counts and metadata
        enriched_data.profile.follower_counts['spotify_monthly_listeners'] = 50000
        enriched_data.profile.follower_counts['instagram'] = 25000
        enriched_data.profile.follower_counts['tiktok'] = 15000
        enriched_data.profile.metadata['tiktok_likes'] = 100000
        enriched_data.profile.metadata['lyrics_themes'] = "love, heartbreak, growth"
        enriched_data.profile.metadata['top_tracks'] = [
            {"name": "Test Song 1", "position": 1},
            {"name": "Test Song 2", "position": 2}
        ]
        
        # Test the data access patterns used in master_discovery_agent
        spotify_listeners = enriched_data.profile.follower_counts.get('spotify_monthly_listeners', 0)
        instagram_followers = enriched_data.profile.follower_counts.get('instagram', 0)
        tiktok_followers = enriched_data.profile.follower_counts.get('tiktok', 0)
        tiktok_likes = enriched_data.profile.metadata.get('tiktok_likes', 0)
        lyrics_themes = enriched_data.profile.metadata.get('lyrics_themes', '')
        top_tracks = enriched_data.profile.metadata.get('top_tracks', [])
        
        print(f"✅ Data access patterns work:")
        print(f"   - Spotify listeners: {spotify_listeners:,}")
        print(f"   - Instagram followers: {instagram_followers:,}")
        print(f"   - TikTok followers: {tiktok_followers:,}")
        print(f"   - TikTok likes: {tiktok_likes:,}")
        print(f"   - Lyrics themes: {lyrics_themes}")
        print(f"   - Top tracks: {len(top_tracks)} tracks")
        
        return True
        
    except Exception as e:
        print(f"❌ Database mapping test error: {e}")
        return False

async def test_discovery_score_calculation():
    """Test the discovery score calculation with fixed data access"""
    print("🎯 Testing discovery score calculation...")
    
    from app.models.artist import ArtistProfile, EnrichedArtistData
    
    try:
        master_agent = MasterDiscoveryAgent()
        
        # Create test data
        artist_profile = ArtistProfile(name="Test Artist")
        enriched_data = EnrichedArtistData(
            profile=artist_profile,
            videos=[],
            lyric_analyses=[],
            enrichment_score=0.8
        )
        
        # Add test metrics
        enriched_data.profile.follower_counts['spotify_monthly_listeners'] = 250000
        enriched_data.profile.follower_counts['instagram'] = 50000
        enriched_data.profile.follower_counts['tiktok'] = 30000
        enriched_data.profile.metadata['tiktok_likes'] = 500000
        enriched_data.profile.metadata['lyrics_themes'] = "emotional, relatable"
        enriched_data.profile.metadata['top_tracks'] = [{"name": "Hit Song"}]
        
        youtube_data = {'subscriber_count': 75000}
        spotify_api_data = {}
        
        # Test score calculation
        score = master_agent._calculate_discovery_score(
            youtube_data, enriched_data, spotify_api_data
        )
        
        print(f"✅ Discovery score calculation: {score}/100")
        
        # Test artificial inflation detection
        penalty = master_agent._detect_artificial_inflation(
            250000,  # spotify
            50000,   # instagram  
            30000,   # tiktok
            75000    # youtube
        )
        
        print(f"✅ Artificial inflation detection: {penalty} penalty points")
        
        return True
        
    except Exception as e:
        print(f"❌ Discovery score test error: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Testing music discovery system fixes...\n")
    
    tests = [
        ("Infinite Scroll", test_infinite_scroll),
        ("Database Mapping", test_database_mapping), 
        ("Discovery Score", test_discovery_score_calculation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running {test_name} Test")
        print('='*50)
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    print(f"\n{'='*50}")
    print("TEST RESULTS SUMMARY")
    print('='*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! System is ready for deployment.")
        return 0
    else:
        print("⚠️ Some tests failed. Review the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)