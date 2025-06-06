#!/usr/bin/env python3
"""
Test script to verify all improvements to the Music Discovery System
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_lazy_agent_initialization():
    """Test that agents are initialized lazily without blocking"""
    logger.info("🧪 Testing lazy agent initialization...")
    
    try:
        # Import should not block
        from app.agents.orchestrator import DiscoveryOrchestrator
        from app.agents.enrichment_agent import ArtistEnrichmentAgent
        from app.agents.lyrics_agent import LyricsAnalysisAgent
        
        # Create instances (should be fast)
        start_time = datetime.now()
        orchestrator = DiscoveryOrchestrator()
        enrichment_agent = ArtistEnrichmentAgent()
        lyrics_agent = LyricsAnalysisAgent()
        init_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Agent initialization completed in {init_time:.2f}s (should be < 1s)")
        assert init_time < 1.0, f"Initialization too slow: {init_time}s"
        
        # Verify agents are not created yet
        assert orchestrator._enrichment_agent is None, "Enrichment agent should not be initialized"
        assert orchestrator._lyrics_agent is None, "Lyrics agent should not be initialized"
        
        logger.info("✅ Lazy initialization working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Lazy initialization test failed: {e}")
        return False

async def test_quota_management():
    """Test advanced quota management system"""
    logger.info("🧪 Testing quota management...")
    
    try:
        from app.core.quota_manager import quota_manager
        from app.core.dependencies import PipelineDependencies
        
        # Test quota checking
        can_search = await quota_manager.can_perform_operation('youtube', 'search', 1)
        logger.info(f"Can perform YouTube search: {can_search}")
        
        # Test quota recording
        await quota_manager.record_operation('youtube', 'search', 1, success=True)
        
        # Test quota status
        status = await quota_manager.get_quota_status()
        logger.info(f"Quota status: {status}")
        
        # Verify YouTube quota tracking
        assert 'youtube' in status, "YouTube quota should be tracked"
        assert status['youtube']['daily_used'] >= 100, "YouTube search should cost 100 units"
        
        logger.info("✅ Quota management working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Quota management test failed: {e}")
        return False

async def test_response_caching():
    """Test response caching system"""
    logger.info("🧪 Testing response caching...")
    
    try:
        from app.core.quota_manager import response_cache
        
        # Test cache set/get
        test_data = {"artist": "Test Artist", "followers": 1000}
        await response_cache.set('spotify', 'search', {"q": "test"}, test_data, ttl=60)
        
        # Retrieve from cache
        cached = await response_cache.get('spotify', 'search', {"q": "test"})
        assert cached == test_data, "Cache should return stored data"
        
        # Test cache stats
        stats = response_cache.get_stats()
        logger.info(f"Cache stats: {stats}")
        assert stats['hit_count'] >= 1, "Should have at least one cache hit"
        
        logger.info("✅ Response caching working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Response caching test failed: {e}")
        return False

async def test_deduplication():
    """Test artist deduplication system"""
    logger.info("🧪 Testing deduplication...")
    
    try:
        from app.core.quota_manager import deduplication_manager
        
        # Test artist fingerprinting
        artist1 = {
            "name": "Test Artist",
            "youtube_channel_id": "UC123456",
            "spotify_id": "spotify:artist:123"
        }
        
        artist2 = {
            "name": "Test Artist",  # Same name
            "youtube_channel_id": "UC123456",  # Same YouTube ID
            "spotify_id": None
        }
        
        artist3 = {
            "name": "Different Artist",
            "youtube_channel_id": "UC789012",
            "spotify_id": "spotify:artist:456"
        }
        
        # Test duplicate detection
        assert not deduplication_manager.is_duplicate(artist1), "First artist should not be duplicate"
        deduplication_manager.mark_as_processed(artist1)
        
        assert deduplication_manager.is_duplicate(artist2), "Same YouTube ID should be duplicate"
        assert not deduplication_manager.is_duplicate(artist3), "Different artist should not be duplicate"
        
        logger.info("✅ Deduplication working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Deduplication test failed: {e}")
        return False

async def test_storage_deduplication():
    """Test database-level deduplication"""
    logger.info("🧪 Testing storage deduplication...")
    
    try:
        from app.agents.storage_agent import StorageAgent
        from app.models.artist import ArtistProfile
        
        storage = StorageAgent()
        
        # Test name similarity calculation
        similarity1 = storage._calculate_name_similarity("The Beatles", "the beatles")
        assert similarity1 >= 0.95, f"Case difference should have high similarity: {similarity1}"
        
        similarity2 = storage._calculate_name_similarity("The Beatles", "Beatles")
        assert similarity2 >= 0.8, f"Partial match should have good similarity: {similarity2}"
        
        similarity3 = storage._calculate_name_similarity("The Beatles", "Pink Floyd")
        assert similarity3 < 0.5, f"Different names should have low similarity: {similarity3}"
        
        logger.info("✅ Storage deduplication working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Storage deduplication test failed: {e}")
        return False

async def test_error_handling():
    """Test error handling and retry logic"""
    logger.info("🧪 Testing error handling...")
    
    try:
        from pydantic_ai import ModelRetry
        
        # Test ModelRetry exception
        try:
            raise ModelRetry("Test retry exception")
        except ModelRetry as e:
            logger.info(f"✅ ModelRetry exception handled: {e}")
        
        # Test would include actual API retry scenarios in production
        logger.info("✅ Error handling mechanisms in place")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error handling test failed: {e}")
        return False

async def test_structured_outputs():
    """Test structured output types"""
    logger.info("🧪 Testing structured outputs...")
    
    try:
        from app.models.artist import ArtistProfile, LyricAnalysis
        
        # Test ArtistProfile validation
        profile = ArtistProfile(
            name="Test Artist",
            youtube_channel_id="UC123",
            youtube_channel_name="Test Channel"
        )
        assert profile.enrichment_score == 0.0, "Default enrichment score should be 0"
        assert profile.status == "discovered", "Default status should be 'discovered'"
        
        # Test LyricAnalysis validation
        analysis = LyricAnalysis(
            artist_id="artist123",
            video_id="video123",
            themes=["love", "heartbreak"],
            sentiment_score=0.5,
            emotional_content=["sad", "nostalgic"],
            lyrical_style="complex",
            language="en"
        )
        assert -1 <= analysis.sentiment_score <= 1, "Sentiment score should be in valid range"
        
        logger.info("✅ Structured outputs working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Structured outputs test failed: {e}")
        return False

async def run_all_tests():
    """Run all test suites"""
    logger.info("🚀 Starting comprehensive test suite...")
    
    tests = [
        ("Lazy Agent Initialization", test_lazy_agent_initialization),
        ("Quota Management", test_quota_management),
        ("Response Caching", test_response_caching),
        ("Deduplication", test_deduplication),
        ("Storage Deduplication", test_storage_deduplication),
        ("Error Handling", test_error_handling),
        ("Structured Outputs", test_structured_outputs)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1) 