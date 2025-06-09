"""
Test script for Crawl4AI integration with music discovery system
"""
import asyncio
import sys
import os
import logging

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.crawl4ai_agent import Crawl4AIAgent
from app.agents.apify_youtube_agent import ApifyYouTubeAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_crawl4ai_social_discovery():
    """Test Crawl4AI social media discovery functionality"""
    print("\n🧪 Testing Crawl4AI Social Media Discovery")
    print("=" * 50)
    
    crawl4ai_agent = Crawl4AIAgent()
    
    # Test artists
    test_artists = [
        ("Billie Eilish", "https://www.youtube.com/@BillieEilish"),
        ("Ed Sheeran", "https://www.youtube.com/@EdSheeran"),
        ("Indie Artist Example", None),  # No channel URL
        ("Unknown New Artist", None)
    ]
    
    for artist_name, channel_url in test_artists:
        print(f"\n🎤 Testing artist: {artist_name}")
        print("-" * 30)
        
        try:
            results = await crawl4ai_agent.discover_artist_social_profiles(
                artist_name=artist_name,
                channel_url=channel_url
            )
            
            print(f"✅ Discovery completed for {artist_name}")
            print(f"   Overall validation score: {results['overall_validation_score']:.2f}")
            
            profiles = results.get("profiles", {})
            scores = results.get("validation_scores", {})
            
            for platform, url in profiles.items():
                if url:
                    score = scores.get(platform, 0)
                    print(f"   {platform.title()}: {url} (score: {score:.2f})")
            
        except Exception as e:
            print(f"❌ Error testing {artist_name}: {str(e)}")


async def test_enhanced_youtube_discovery():
    """Test enhanced YouTube discovery with Crawl4AI integration"""
    print("\n🧪 Testing Enhanced YouTube Discovery with Crawl4AI")
    print("=" * 50)
    
    # Check if Apify is configured
    if not os.getenv('APIFY_API_TOKEN'):
        print("⚠️ APIFY_API_TOKEN not set - skipping YouTube discovery test")
        print("   Set APIFY_API_TOKEN environment variable to test YouTube integration")
        return
    
    youtube_agent = ApifyYouTubeAgent()
    
    # Test undiscovered artist discovery
    print("\n🔍 Discovering undiscovered artists...")
    
    try:
        # Discover artists
        undiscovered_artists = await youtube_agent.discover_undiscovered_artists(max_results=10)
        
        if undiscovered_artists:
            print(f"\n✅ Found {len(undiscovered_artists)} undiscovered artists")
            
            # Show top 3 artists
            for i, artist in enumerate(undiscovered_artists[:3], 1):
                print(f"\n🎵 Artist {i}: {artist.get('channel_title', 'Unknown')}")
                print(f"   View Count: {artist.get('view_count', 0):,}")
                print(f"   Undiscovered Score: {artist.get('undiscovered_score', 0):.2f}")
                
                # Check social media
                social_media = artist.get('social_media', {})
                if social_media:
                    print(f"   Social Media Validation: {social_media.get('validation_score', 0):.2f}")
                    if social_media.get('instagram'):
                        print(f"   Instagram: {social_media['instagram']}")
                    if social_media.get('tiktok'):
                        print(f"   TikTok: {social_media['tiktok']}")
        else:
            print("❌ No undiscovered artists found")
            
    except Exception as e:
        print(f"❌ Error in YouTube discovery: {str(e)}")


async def test_website_extraction():
    """Test artist website information extraction"""
    print("\n🧪 Testing Artist Website Extraction")
    print("=" * 50)
    
    crawl4ai_agent = Crawl4AIAgent()
    
    # Test with a known artist website
    test_websites = [
        "https://www.billieeilish.com",
        "https://www.edsheeran.com"
    ]
    
    for website_url in test_websites:
        print(f"\n🌐 Testing website: {website_url}")
        print("-" * 30)
        
        try:
            info = await crawl4ai_agent.extract_artist_website_info(website_url)
            
            if info:
                print(f"✅ Extracted website information")
                print(f"   Title: {info.get('title', 'N/A')}")
                
                if info.get('contact_info', {}).get('emails'):
                    print(f"   Emails found: {len(info['contact_info']['emails'])}")
                
                if info.get('social_links'):
                    print("   Social links found:")
                    for platform, handle in info['social_links'].items():
                        print(f"     - {platform}: {handle}")
                
                if info.get('bio'):
                    print(f"   Bio: {info['bio'][:100]}...")
            else:
                print("❌ No information extracted")
                
        except Exception as e:
            print(f"❌ Error extracting website info: {str(e)}")


async def main():
    """Run all tests"""
    print("🏯 Crawl4AI Integration Test Suite")
    print("=" * 50)
    
    # Run tests
    await test_crawl4ai_social_discovery()
    await test_enhanced_youtube_discovery()
    await test_website_extraction()
    
    print("\n✅ All tests completed!")
    print("\nNext steps:")
    print("1. Deploy the updated system with Crawl4AI integration")
    print("2. Monitor performance and accuracy of social media discovery")
    print("3. Adjust validation thresholds based on results")


if __name__ == "__main__":
    asyncio.run(main()) 