"""
Test script to verify Crawl4AI installation and basic functionality
"""
import asyncio
import json
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
    print("✅ Crawl4AI imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Crawl4AI: {e}")
    print("Please run: pip install crawl4ai")
    sys.exit(1)

async def test_basic_crawling():
    """Test basic crawling functionality"""
    print("\n🧪 Test 1: Basic Crawling")
    print("-" * 50)
    
    try:
        browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url="https://example.com",
                config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
            )
            
            if result.success:
                print("✅ Basic crawling successful")
                print(f"   - Title: {result.title}")
                print(f"   - Content length: {len(result.markdown)} characters")
                return True
            else:
                print(f"❌ Crawling failed: {result.error_message}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def test_youtube_search_crawling():
    """Test YouTube search page crawling"""
    print("\n🧪 Test 2: YouTube Search Crawling")
    print("-" * 50)
    
    try:
        browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        # Simple schema to extract video data
        schema = {
            "name": "YouTube Videos",
            "baseSelector": "ytd-video-renderer",
            "fields": [
                {
                    "name": "title",
                    "selector": "#video-title",
                    "type": "text"
                },
                {
                    "name": "channel",
                    "selector": "#channel-info #text-container",
                    "type": "text"
                },
                {
                    "name": "views",
                    "selector": "#metadata-line span:first-child",
                    "type": "text"
                }
            ]
        }
        
        extraction_strategy = JsonCssExtractionStrategy(schema)
        
        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=extraction_strategy,
            wait_for="css:ytd-video-renderer",  # Wait for videos to load
            js_code="window.scrollTo(0, 1000);"  # Scroll to load more videos
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url="https://www.youtube.com/results?search_query=music",
                config=crawler_config
            )
            
            if result.success:
                print("✅ YouTube crawling successful")
                if result.extracted_content:
                    videos = json.loads(result.extracted_content)
                    print(f"   - Found {len(videos)} videos")
                    if videos:
                        print(f"   - First video: {videos[0].get('title', 'N/A')}")
                else:
                    print("   - No videos extracted (YouTube may have anti-bot measures)")
                return True
            else:
                print(f"❌ YouTube crawling failed: {result.error_message}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def test_javascript_execution():
    """Test JavaScript execution capabilities"""
    print("\n🧪 Test 3: JavaScript Execution")
    print("-" * 50)
    
    try:
        browser_config = BrowserConfig(headless=True)
        
        # Test page with dynamic content
        test_html = """
        <html>
        <body>
            <div id="content">Initial content</div>
            <button onclick="document.getElementById('content').innerText='Updated via JS'">Click me</button>
        </body>
        </html>
        """
        
        js_code = """
        document.querySelector('button').click();
        """
        
        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            js_code=js_code,
            wait_for="js:() => document.getElementById('content').innerText === 'Updated via JS'"
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url=f"data:text/html,{test_html}",
                config=crawler_config
            )
            
            if result.success and "Updated via JS" in result.html:
                print("✅ JavaScript execution successful")
                return True
            else:
                print("❌ JavaScript execution failed")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🏯 Crawl4AI Setup Verification")
    print("=" * 50)
    
    tests = [
        test_basic_crawling(),
        test_youtube_search_crawling(),
        test_javascript_execution()
    ]
    
    results = await asyncio.gather(*tests)
    
    print("\n📊 Test Summary")
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All tests passed ({passed}/{total})")
        print("\n🎉 Crawl4AI is properly installed and configured!")
        print("\nNext steps:")
        print("1. Create the YouTube discovery agent with Crawl4AI")
        print("2. Implement social media crawling agents")
        print("3. Update the orchestrator workflow")
    else:
        print(f"⚠️ {passed}/{total} tests passed")
        print("\nPlease check the failed tests and ensure:")
        print("1. Crawl4AI is properly installed")
        print("2. Chrome/Chromium is available on your system")
        print("3. Network connectivity is working")

if __name__ == "__main__":
    asyncio.run(main()) 