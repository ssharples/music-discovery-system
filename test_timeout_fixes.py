#!/usr/bin/env python3
"""
Test script to verify timeout fixes for Apify integration
"""
import os
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.agents.apify_youtube_agent import ApifyYouTubeAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_timeout_resilience():
    """Test the improved timeout handling in Apify agent"""
    
    load_dotenv()
    
    print("🧪 Testing Apify Timeout Fixes")
    print("=" * 50)
    
    agent = ApifyYouTubeAgent()
    
    if not agent.apify_api_token:
        print("❌ APIFY_API_TOKEN not configured!")
        return False
    
    print("✅ APIFY_API_TOKEN configured")
    
    # Test 1: Small search (should work)
    print("\n🔍 Test 1: Small search (20 results)")
    try:
        start_time = datetime.now()
        videos = await agent.search_music_content(
            keywords=["indie music"],
            max_results=20,
            upload_date="week"
        )
        duration = (datetime.now() - start_time).total_seconds()
        
        if videos:
            print(f"✅ Small search successful: {len(videos)} videos in {duration:.1f}s")
        else:
            print(f"⚠️ Small search returned no results in {duration:.1f}s")
            
    except Exception as e:
        print(f"❌ Small search failed: {e}")
    
    # Test 2: Medium search with batch fallback
    print("\n🔍 Test 2: Medium search (50 results)")
    try:
        start_time = datetime.now()
        
        # Create a mock deps object for the discover_artists method
        class MockDeps:
            pass
        
        deps = MockDeps()
        
        channels = await agent.discover_artists(
            deps=deps,
            query="new music 2024",
            max_results=50
        )
        duration = (datetime.now() - start_time).total_seconds()
        
        if channels:
            print(f"✅ Medium search successful: {len(channels)} channels in {duration:.1f}s")
            
            # Show some results
            for i, channel in enumerate(channels[:3]):
                artist_name = channel.get('extracted_artist_name') or channel.get('channel_title', 'Unknown')
                quality = channel.get('quality_score', 0)
                print(f"  {i+1}. {artist_name} (quality: {quality:.2f})")
                
        else:
            print(f"⚠️ Medium search returned no results in {duration:.1f}s")
            
    except Exception as e:
        print(f"❌ Medium search failed: {e}")
    
    # Test 3: Cost estimation
    print("\n💰 Test 3: Cost estimation")
    try:
        cost_50 = agent.get_cost_estimate(50)
        cost_100 = agent.get_cost_estimate(100)
        cost_1000 = agent.get_cost_estimate(1000)
        
        print(f"✅ Cost estimates:")
        print(f"  50 videos: ${cost_50:.4f}")
        print(f"  100 videos: ${cost_100:.4f}")
        print(f"  1000 videos: ${cost_1000:.4f}")
        
    except Exception as e:
        print(f"❌ Cost estimation failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Timeout Fix Summary:")
    print("- Increased HTTP timeouts (30s → 120s for start, 60s → 180s for results)")
    print("- Extended max wait time (300s → 600s)")
    print("- Added retry logic for actor start (3 attempts)")
    print("- Improved error handling for specific timeout errors")
    print("- Added batch fallback for large searches")
    print("- Better logging and progress tracking")
    
    return True

async def test_fallback_mechanisms():
    """Test the fallback mechanisms specifically"""
    
    print("\n🔄 Testing Fallback Mechanisms")
    print("=" * 50)
    
    agent = ApifyYouTubeAgent()
    
    if not agent.apify_api_token:
        print("❌ APIFY_API_TOKEN not configured!")
        return False
    
    # Test the batch fallback method directly
    print("🔍 Testing batch fallback method...")
    try:
        start_time = datetime.now()
        
        videos = await agent._discover_with_smaller_batches("electronic music", 40)
        duration = (datetime.now() - start_time).total_seconds()
        
        if videos:
            print(f"✅ Batch fallback successful: {len(videos)} videos in {duration:.1f}s")
            
            # Check for duplicates
            video_ids = [v.get('video_id') for v in videos if v.get('video_id')]
            unique_ids = set(video_ids)
            
            print(f"📊 Duplicate check: {len(video_ids)} total, {len(unique_ids)} unique")
            
        else:
            print(f"⚠️ Batch fallback returned no results in {duration:.1f}s")
            
    except Exception as e:
        print(f"❌ Batch fallback failed: {e}")
    
    return True

if __name__ == "__main__":
    print("🚀 Apify Timeout Fixes Test Suite")
    print("Testing the improvements to handle 504 Gateway Timeout errors")
    
    async def run_all_tests():
        success1 = await test_timeout_resilience()
        success2 = await test_fallback_mechanisms()
        return success1 and success2
    
    success = asyncio.run(run_all_tests())
    
    if success:
        print("\n✅ All tests completed!")
        print("\n🔧 If you're still getting 504 errors:")
        print("1. Check your Coolify/deployment timeout settings")
        print("2. Consider reducing max_results further (try 15-20)")
        print("3. Monitor Apify console for actor run status")
        print("4. Check network connectivity to Apify servers")
    else:
        print("\n❌ Tests had issues. Check your APIFY_API_TOKEN and network connection.") 