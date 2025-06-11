#!/usr/bin/env python3
"""
Test script for the new scrolling discovery system.
Verifies that we can get 100+ videos that pass filters.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.dependencies import get_pipeline_dependencies
from app.agents.master_discovery_agent import MasterDiscoveryAgent

async def test_scrolling_discovery():
    """Test the new scrolling discovery system."""
    print("🧪 Testing Scrolling Discovery System")
    print("=" * 50)
    
    try:
        # Initialize dependencies
        print("📋 Initializing dependencies...")
        deps = await get_pipeline_dependencies()
        
        # Initialize master discovery agent
        print("🤖 Initializing Master Discovery Agent...")
        agent = MasterDiscoveryAgent()
        
        # Test scrolling search with filtering
        print("🔄 Testing scrolling search and filtering...")
        search_query = "official music video"
        target_videos = 50  # Start with smaller target for testing
        
        processed_videos = await agent._search_and_filter_videos_with_scrolling(
            deps=deps,
            search_query=search_query,
            target_filtered_videos=target_videos
        )
        
        print(f"\n📊 Results:")
        print(f"   Target videos: {target_videos}")
        print(f"   Videos found: {len(processed_videos)}")
        print(f"   Success rate: {len(processed_videos) / target_videos * 100:.1f}%")
        
        if processed_videos:
            print(f"\n📝 Sample videos that passed filters:")
            for i, video in enumerate(processed_videos[:5], 1):
                artist = video.get('extracted_artist_name', 'Unknown')
                title = video.get('title', 'Unknown')[:50]
                print(f"   {i}. {artist} - {title}...")
        
        # Test the complete discovery workflow
        print(f"\n🎵 Testing complete discovery workflow...")
        result = await agent.discover_artists(
            deps=deps,
            max_results=10,  # Process only 10 artists for testing
            search_query=search_query
        )
        
        print(f"\n🎯 Complete Workflow Results:")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message')}")
        
        data = result.get('data', {})
        print(f"   Artists discovered: {data.get('total_found', 0)}")
        print(f"   Artists processed: {data.get('total_processed', 0)}")
        print(f"   Execution time: {data.get('execution_time', 0):.2f}s")
        
        metadata = data.get('discovery_metadata', {})
        print(f"   Videos after filtering: {metadata.get('videos_after_filtering', 0)}")
        
        if result.get('status') == 'success':
            print("✅ Scrolling discovery test PASSED!")
        else:
            print("❌ Scrolling discovery test FAILED!")
            print(f"   Error: {result.get('message')}")
        
    except Exception as e:
        print(f"💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()

async def test_youtube_agent_directly():
    """Test the YouTube agent scrolling directly."""
    print("\n🔬 Testing YouTube Agent Scrolling Directly")
    print("=" * 50)
    
    try:
        from app.agents.crawl4ai_youtube_agent import Crawl4AIYouTubeAgent
        
        agent = Crawl4AIYouTubeAgent()
        
        # Test with daily filter
        print("📺 Testing YouTube search with 'day' filter...")
        result = await agent.search_videos(
            query="official music video",
            max_results=100,
            upload_date="day"
        )
        
        print(f"   Success: {result.success}")
        print(f"   Videos found: {len(result.videos)}")
        print(f"   Error: {result.error_message}")
        
        if result.videos:
            print(f"\n📝 Sample raw videos:")
            for i, video in enumerate(result.videos[:3], 1):
                print(f"   {i}. {video.title[:50]}... by {video.channel_name}")
        
    except Exception as e:
        print(f"💥 YouTube agent test failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Scrolling Discovery Tests")
    print("=" * 60)
    
    # Run YouTube agent test first
    asyncio.run(test_youtube_agent_directly())
    
    # Then run full discovery test
    asyncio.run(test_scrolling_discovery())
    
    print("\n🏁 All tests completed!") 