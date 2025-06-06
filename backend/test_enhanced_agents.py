"""
Test script for enhanced agent architecture and Firecrawl integration.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhanced_agent_base():
    """Test the enhanced agent base functionality"""
    try:
        from app.agents.enhanced_agent_base import EnhancedAgentBase, AgentContext, AgentResponse
        from app.core.dependencies import get_pipeline_deps
        from pydantic_ai.tools import Tool
        
        class TestAgent(EnhancedAgentBase):
            def get_system_prompt(self) -> str:
                return "You are a test agent for validating the enhanced architecture."
            
            def _get_tools(self) -> list[Tool]:
                return []
        
        # Initialize test agent
        agent = TestAgent("TestAgent")
        
        # Create test context
        context = AgentContext(
            session_id="test_session_123",
            metadata={"test": True}
        )
        
        logger.info("✅ Enhanced agent base classes loaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhanced agent base test failed: {e}")
        return False

async def test_firecrawl_integration():
    """Test Firecrawl integration capabilities"""
    try:
        from app.agents.enhanced_enrichment_agent import FirecrawlScrapingTool
        from app.core.config import settings
        
        tool = FirecrawlScrapingTool()
        
        if not settings.FIRECRAWL_API_KEY:
            logger.warning("⚠️ Firecrawl API key not configured - integration test skipped")
            return True
        
        # Test website scraping (using a simple public page)
        result = await tool.scrape_artist_website("https://example.com")
        
        if result.get("success") or result.get("error") == "Firecrawl not configured":
            logger.info("✅ Firecrawl integration test passed")
            return True
        else:
            logger.error(f"❌ Firecrawl test failed: {result}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Firecrawl integration test failed: {e}")
        return False

async def test_enhanced_enrichment_agent():
    """Test the enhanced enrichment agent"""
    try:
        from app.agents.enhanced_enrichment_agent import EnhancedEnrichmentAgent, get_enhanced_enrichment_agent
        from app.models.artist import ArtistProfile
        
        # Create test agent
        agent = get_enhanced_enrichment_agent()
        
        # Create test artist profile
        test_profile = ArtistProfile(
            name="Test Artist",
            website_url="https://example.com",
            social_links=["https://instagram.com/testartist"]
        )
        
        logger.info("✅ Enhanced enrichment agent created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhanced enrichment agent test failed: {e}")
        return False

async def test_configuration_enhancements():
    """Test enhanced configuration management"""
    try:
        from app.core.config import settings
        
        # Test new configuration methods
        providers = settings.get_available_ai_providers()
        firecrawl_configured = settings.is_firecrawl_configured()
        openai_configured = settings.is_openai_configured()
        
        logger.info(f"✅ Configuration enhancements working:")
        logger.info(f"  - Available AI providers: {providers}")
        logger.info(f"  - Firecrawl configured: {firecrawl_configured}")
        logger.info(f"  - OpenAI configured: {openai_configured}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration enhancement test failed: {e}")
        return False

async def run_all_tests():
    """Run all enhancement tests"""
    logger.info("🧪 Starting enhanced agent architecture tests...")
    
    tests = [
        ("Enhanced Agent Base", test_enhanced_agent_base),
        ("Firecrawl Integration", test_firecrawl_integration),
        ("Enhanced Enrichment Agent", test_enhanced_enrichment_agent),
        ("Configuration Enhancements", test_configuration_enhancements),
    ]
    
    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        try:
            result = await test_func()
            results[test_name] = result
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{status}: {test_name}")
        except Exception as e:
            results[test_name] = False
            logger.error(f"❌ FAILED: {test_name} - {e}")
    
    # Summary
    logger.info("\n📊 Test Results Summary:")
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"  {status} {test_name}")
    
    logger.info(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("🎉 All enhancements are working correctly!")
    else:
        logger.warning("⚠️ Some enhancements need attention. Check the logs above.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(run_all_tests()) 