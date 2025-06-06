#!/usr/bin/env python3
"""
Test script to verify Firecrawl import and basic functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings

def test_firecrawl_import():
    """Test if Firecrawl can be imported correctly"""
    print("🔥 Testing Firecrawl import...")
    
    try:
        from firecrawl import FirecrawlApp
        print("✅ FirecrawlApp imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import FirecrawlApp: {e}")
        return False

def test_firecrawl_configuration():
    """Test Firecrawl configuration"""
    print("\n🔧 Testing Firecrawl configuration...")
    
    api_key_set = bool(settings.FIRECRAWL_API_KEY)
    configured = settings.is_firecrawl_configured()
    
    print(f"API Key set: {api_key_set}")
    print(f"Configured: {configured}")
    print(f"API Key value: {'***' + settings.FIRECRAWL_API_KEY[-4:] if settings.FIRECRAWL_API_KEY else 'NOT SET'}")
    
    return configured

def test_firecrawl_initialization():
    """Test if FirecrawlApp can be initialized"""
    print("\n🚀 Testing Firecrawl initialization...")
    
    if not settings.is_firecrawl_configured():
        print("⚠️ Skipping initialization test - API key not configured")
        return False
    
    try:
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
        print("✅ FirecrawlApp initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize FirecrawlApp: {e}")
        return False

def test_enhanced_enrichment_agent():
    """Test the enhanced enrichment agent with new Firecrawl import"""
    print("\n🎤 Testing Enhanced Enrichment Agent...")
    
    try:
        from app.agents.enhanced_enrichment_agent_simple import SimpleEnhancedEnrichmentAgent
        agent = SimpleEnhancedEnrichmentAgent()
        print("✅ Enhanced Enrichment Agent imported and initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import/initialize Enhanced Enrichment Agent: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Firecrawl Fix Test Suite")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_firecrawl_import),
        ("Configuration Test", test_firecrawl_configuration),
        ("Initialization Test", test_firecrawl_initialization),
        ("Enhanced Agent Test", test_enhanced_enrichment_agent)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Firecrawl is ready to use.")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        
        if not settings.is_firecrawl_configured():
            print("\n💡 To fix the configuration issue:")
            print("1. Sign up at https://firecrawl.dev to get an API key")
            print("2. Set the FIRECRAWL_API_KEY environment variable")
            print("3. Add FIRECRAWL_API_KEY=fc-your-api-key to your .env file")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 