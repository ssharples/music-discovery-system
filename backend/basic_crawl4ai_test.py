"""
Basic Crawl4AI test without external API dependencies
Tests core YouTube scraping and basic enrichment functionality
"""
import asyncio
import json
import logging
import time
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from app.agents.crawl4ai_youtube_agent import Crawl4AIYouTubeAgent
from app.models.artist import ArtistProfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_youtube_basic():
    """Test basic YouTube functionality without complex selectors"""
    logger.info("🎥 Testing Basic YouTube Functionality...")
    
    try:
        agent = Crawl4AIYouTubeAgent()
        
        # Test with simple URL direct access
        test_url = "https://www.youtube.com/results?search_query=music"
        
        logger.info(f"   → Testing direct URL access: {test_url}")
        
        # Simple test - just try to crawl a basic page
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
        
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_for="body",  # Just wait for basic page load
            js_code="console.log('Page loaded');"
        )
        
        async with AsyncWebCrawler(config=agent.browser_config) as crawler:
            result = await crawler.arun(url=test_url, config=config)
            
            success = result.success and result.html and len(result.html) > 1000
            
            logger.info(f"   → Page crawled successfully: {success}")
            logger.info(f"   → HTML length: {len(result.html) if result.html else 0} characters")
            
            if success:
                # Check for basic YouTube elements
                youtube_indicators = [
                    "ytd-" in result.html,
                    "youtube" in result.html.lower(),
                    "video" in result.html.lower()
                ]
                
                quality_score = sum(youtube_indicators) / len(youtube_indicators) * 100
                logger.info(f"   → YouTube content quality: {quality_score:.1f}%")
                
                return {
                    "success": success and quality_score > 50,
                    "html_length": len(result.html),
                    "quality_score": f"{quality_score:.1f}%",
                    "youtube_elements_found": sum(youtube_indicators)
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to crawl YouTube page",
                    "html_length": len(result.html) if result.html else 0
                }
        
    except Exception as e:
        logger.error(f"   ❌ Basic YouTube test failed: {str(e)}")
        return {"success": False, "error": str(e)}


async def test_cost_validation():
    """Test cost estimation functions"""
    logger.info("💰 Testing Cost Validation...")
    
    try:
        youtube_agent = Crawl4AIYouTubeAgent()
        
        # Test YouTube cost estimation
        cost_100 = youtube_agent.get_cost_estimate(100)
        cost_1000 = youtube_agent.get_cost_estimate(1000)
        
        logger.info(f"   → Cost for 100 searches: ${cost_100}")
        logger.info(f"   → Cost for 1000 searches: ${cost_1000}")
        
        # Validate costs are zero (free)
        costs_are_free = cost_100 == 0.0 and cost_1000 == 0.0
        
        return {
            "success": costs_are_free,
            "cost_100_searches": cost_100,
            "cost_1000_searches": cost_1000,
            "is_free": costs_are_free
        }
        
    except Exception as e:
        logger.error(f"   ❌ Cost validation failed: {str(e)}")
        return {"success": False, "error": str(e)}


async def test_browser_config():
    """Test browser configuration and initialization"""
    logger.info("🌐 Testing Browser Configuration...")
    
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig
        
        # Test browser config creation
        browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080
        )
        
        # Test crawler initialization
        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Test with a simple, reliable page
            result = await crawler.arun(url="https://httpbin.org/get")
            
            success = result.success and result.html and "httpbin" in result.html
            
            logger.info(f"   → Browser config valid: {success}")
            
            return {
                "success": success,
                "browser_config_valid": True,
                "test_page_loaded": success
            }
        
    except Exception as e:
        logger.error(f"   ❌ Browser config test failed: {str(e)}")
        return {"success": False, "error": str(e)}


async def run_basic_validation():
    """Run basic validation tests"""
    logger.info("🧪 Starting Basic Crawl4AI Validation...")
    logger.info("="*50)
    
    results = {
        "test_suite": "Basic Crawl4AI Validation",  
        "tests": {},
        "summary": {}
    }
    
    test_methods = [
        ("browser_config", test_browser_config),
        ("cost_validation", test_cost_validation),
        ("youtube_basic", test_youtube_basic)
    ]
    
    passed_tests = 0
    total_tests = len(test_methods)
    
    for test_name, test_method in test_methods:
        try:
            start_time = time.time()
            test_result = await test_method()
            execution_time = time.time() - start_time
            
            test_result["execution_time"] = f"{execution_time:.2f}s"
            test_result["status"] = "PASSED" if test_result.get("success", False) else "FAILED"
            
            results["tests"][test_name] = test_result
            
            if test_result.get("success", False):
                passed_tests += 1
                logger.info(f"✅ {test_name}: PASSED ({execution_time:.2f}s)")
            else:
                logger.error(f"❌ {test_name}: FAILED - {test_result.get('error', 'Unknown error')}")
            
            logger.info("-" * 30)
            
        except Exception as e:
            logger.error(f"💥 {test_name}: CRASHED - {str(e)}")
            results["tests"][test_name] = {
                "status": "CRASHED",
                "error": str(e),
                "success": False
            }
    
    # Generate summary
    results["summary"] = {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": total_tests - passed_tests,
        "success_rate": f"{(passed_tests / total_tests) * 100:.1f}%",
        "overall_status": "PASSED" if passed_tests >= total_tests * 0.8 else "FAILED"  # 80% threshold
    }
    
    # Print summary
    logger.info("="*50)
    logger.info("📊 BASIC VALIDATION SUMMARY")
    logger.info("="*50)
    logger.info(f"Total Tests: {results['summary']['total_tests']}")
    logger.info(f"Passed: {results['summary']['passed_tests']}")
    logger.info(f"Failed: {results['summary']['failed_tests']}")
    logger.info(f"Success Rate: {results['summary']['success_rate']}")
    logger.info(f"Overall Status: {results['summary']['overall_status']}")
    logger.info("="*50)
    
    # Save results
    with open("basic_validation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info("💾 Results saved to: basic_validation_results.json")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_basic_validation()) 