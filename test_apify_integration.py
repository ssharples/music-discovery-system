#!/usr/bin/env python3
"""
Test script for Apify YouTube integration
Run this to verify the Apify YouTube scraper is working correctly
"""

import os
import sys
import json
from dotenv import load_dotenv

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.agents.apify_youtube_agent import ApifyYouTubeAgent

async def test_apify_youtube_agent():
    """Test the Apify YouTube agent functionality"""
    
    # Load environment variables
    load_dotenv()
    
    print("🧪 Testing Apify YouTube Agent Integration")
    print("=" * 50)
    
    # Initialize the agent
    agent = ApifyYouTubeAgent()
    
    # Check if API token is configured
    if not agent.apify_api_token:
        print("❌ APIFY_API_TOKEN not configured!")
        print("Please add APIFY_API_TOKEN to your .env file")
        print("Get your token from: https://console.apify.com/account/integrations")
        return False
    
    print("✅ APIFY_API_TOKEN configured")
    
    # Test 1: Search for music content
    print("\n🎵 Test 1: Searching for music content...")
    try:
        # Search for a small amount to test (cost-effective)
        results = await agent.search_music_content(
            keywords=["indie rock 2024"],
            max_results=5,  # Small test to minimize cost
            upload_date="month"
        )
        
        if results:
            print(f"✅ Successfully found {len(results)} music videos")
            
            # Show sample result
            sample = results[0]
            print(f"\nSample result:")
            print(f"  Title: {sample.get('title', 'N/A')}")
            print(f"  Channel: {sample.get('channel_title', 'N/A')}")
            print(f"  Extracted Artist: {sample.get('extracted_artist_name', 'N/A')}")
            print(f"  Views: {sample.get('view_count', 0):,}")
            print(f"  Duration: {sample.get('duration_seconds', 0)} seconds")
            
            # Calculate cost
            cost = agent.get_cost_estimate(len(results))
            print(f"\n💰 Cost for this test: ${cost:.4f}")
            
        else:
            print("❌ No results returned")
            return False
            
    except Exception as e:
        print(f"❌ Error during search test: {str(e)}")
        return False
    
    # Test 2: Get trending music
    print("\n📈 Test 2: Getting trending music...")
    try:
        trending = await agent.get_trending_music(max_results=3)  # Small test
        
        if trending:
            print(f"✅ Successfully found {len(trending)} trending music videos")
            
            sample = trending[0]
            print(f"\nSample trending result:")
            print(f"  Title: {sample.get('title', 'N/A')}")
            print(f"  Views: {sample.get('view_count', 0):,}")
            
        else:
            print("⚠️  No trending music found (this might be normal)")
            
    except Exception as e:
        print(f"❌ Error during trending test: {str(e)}")
        return False
    
    print("\n🎉 All tests completed successfully!")
    print("\nNext steps:")
    print("1. Update your orchestrator to use ApifyYouTubeAgent instead of the official API")
    print("2. Monitor costs at: https://console.apify.com/account/billing")
    print("3. The scraper costs $0.50 per 1,000 videos (much cheaper than quota issues)")
    
    return True

def show_integration_instructions():
    """Show instructions for integrating into the main system"""
    
    print("\n" + "=" * 60)
    print("📋 INTEGRATION INSTRUCTIONS")
    print("=" * 60)
    
    print("""
1. SET UP APIFY ACCOUNT:
   - Sign up at: https://apify.com/
   - Get your API token from: https://console.apify.com/account/integrations
   - Add to .env file: APIFY_API_TOKEN=your_token_here

2. UPDATE YOUR ORCHESTRATOR:
   In backend/app/agents/orchestrator.py, replace YouTube agent usage:
   
   # OLD:
   from app.agents.youtube_agent import YouTubeAgent
   youtube_agent = YouTubeAgent()
   
   # NEW:
   from app.agents.apify_youtube_agent import ApifyYouTubeAgent
   youtube_agent = ApifyYouTubeAgent()

3. COST MONITORING:
   - Monitor usage at: https://console.apify.com/account/billing
   - Current rate: $0.50 per 1,000 videos
   - Much cheaper than hitting YouTube API quotas!

4. FEATURES AVAILABLE:
   - search_music_content() - Search by keywords
   - get_channel_videos() - Get videos from specific channels  
   - get_trending_music() - Get trending music content
   - get_cost_estimate() - Calculate expected costs

5. BENEFITS:
   ✅ No more quota limitations
   ✅ 97% success rate
   ✅ 10+ videos per second processing
   ✅ Comprehensive video data
   ✅ Artist name extraction built-in
   ✅ Cost-effective pricing
""")

if __name__ == "__main__":
    print("🏯 Apify YouTube Scraper Integration Test")
    print("Based on: https://apify.com/apidojo/youtube-scraper")
    
    import asyncio
    success = asyncio.run(test_apify_youtube_agent())
    
    if success:
        show_integration_instructions()
    else:
        print("\n❌ Tests failed. Please check your configuration and try again.")
        
    print("\nFor support: apidojo10@gmail.com") 