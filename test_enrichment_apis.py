#!/usr/bin/env python3
"""
Test script to verify Spotify and Firecrawl API configurations
"""
import asyncio
import httpx
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import settings
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.config import settings

async def test_spotify_api():
    """Test Spotify API configuration"""
    logger.info("🎵 Testing Spotify API...")
    
    if not settings.is_spotify_configured():
        logger.error("❌ Spotify not configured")
        logger.info(f"   CLIENT_ID: {bool(settings.SPOTIFY_CLIENT_ID)}")
        logger.info(f"   CLIENT_SECRET: {bool(settings.SPOTIFY_CLIENT_SECRET)}")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            # Test authentication
            auth_url = "https://accounts.spotify.com/api/token"
            auth_data = {
                "grant_type": "client_credentials",
                "client_id": settings.SPOTIFY_CLIENT_ID,
                "client_secret": settings.SPOTIFY_CLIENT_SECRET
            }
            
            auth_response = await client.post(auth_url, data=auth_data)
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
            
            # Test search
            search_url = "https://api.spotify.com/v1/search"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"q": "test artist", "type": "artist", "limit": 1}
            
            search_response = await client.get(search_url, headers=headers, params=params)
            search_response.raise_for_status()
            
            results = search_response.json()
            artists_count = len(results["artists"]["items"])
            
            logger.info(f"✅ Spotify API working! Found {artists_count} test results")
            return True
            
    except Exception as e:
        logger.error(f"❌ Spotify API test failed: {e}")
        return False

async def test_firecrawl_api():
    """Test Firecrawl API configuration"""
    logger.info("🔥 Testing Firecrawl API...")
    
    if not settings.is_firecrawl_configured():
        logger.error(f"❌ Firecrawl not configured - API key: {bool(settings.FIRECRAWL_API_KEY)}")
        return False
    
    try:
        # Try importing firecrawl
        import firecrawl
        
        # Test with a simple scrape
        app = firecrawl.FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
        
        # Test scraping a simple page
        result = app.scrape_url(
            "https://example.com",
            params={
                'formats': ['markdown'],
                'timeout': 10000,
                'waitFor': 2000
            }
        )
        
        if result and result.get('success'):
            content_length = len(result.get('markdown', ''))
            logger.info(f"✅ Firecrawl API working! Scraped {content_length} characters")
            return True
        else:
            logger.error(f"❌ Firecrawl scraping failed: {result}")
            return False
            
    except ImportError:
        logger.error("❌ Firecrawl library not installed")
        return False
    except Exception as e:
        logger.error(f"❌ Firecrawl API test failed: {e}")
        return False

async def test_api_configurations():
    """Test all API configurations"""
    logger.info(f"🧪 Testing API configurations at {datetime.now()}")
    logger.info("=" * 50)
    
    # Test each API
    spotify_ok = await test_spotify_api()
    firecrawl_ok = await test_firecrawl_api()
    
    # Summary
    logger.info("=" * 50)
    logger.info("📊 Test Results Summary:")
    logger.info(f"   Spotify API: {'✅ Working' if spotify_ok else '❌ Failed'}")
    logger.info(f"   Firecrawl API: {'✅ Working' if firecrawl_ok else '❌ Failed'}")
    
    if spotify_ok and firecrawl_ok:
        logger.info("🎉 All APIs are configured and working!")
    else:
        logger.warning("⚠️ Some APIs need configuration. Check your environment variables.")
        
    return spotify_ok, firecrawl_ok

if __name__ == "__main__":
    asyncio.run(test_api_configurations()) 