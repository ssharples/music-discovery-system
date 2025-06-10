#!/usr/bin/env python3
"""
Production Music Discovery System Test & Starter
Tests the deployed system on Coolify and starts the discovery process.
"""

import asyncio
import json
import time
import requests
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Production configuration
PRODUCTION_BASE_URL = "https://your-coolify-domain.com"  # Update with your actual domain
API_TIMEOUT = 120  # Longer timeout for production

class ProductionDiscoveryTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = API_TIMEOUT
        
    def test_system_health(self):
        """Test production system health"""
        print("🔍 Testing Production System Health")
        print("=" * 50)
        
        # Test 1: Basic health check
        try:
            response = self.session.get(f"{self.base_url}/health")
            print(f"✅ Health Check: {response.status_code}")
            if response.status_code == 200:
                health_data = response.json()
                print(f"   Status: {health_data.get('status', 'unknown')}")
                print(f"   Environment: {health_data.get('environment', 'unknown')}")
            else:
                print(f"❌ Health check failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
        
        # Test 2: Master Discovery Status
        try:
            response = self.session.get(f"{self.base_url}/api/master-discovery/status")
            print(f"✅ Master Discovery Status: {response.status_code}")
            if response.status_code == 200:
                status_data = response.json()
                print(f"   Version: {status_data['master_discovery_agent']['version']}")
                print(f"   Components: {len(status_data['master_discovery_agent']['components'])}")
                print(f"   Supported Platforms: {len(status_data['master_discovery_agent']['supported_platforms'])}")
            else:
                print(f"❌ Master discovery status failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Master discovery status error: {e}")
            return False
        
        # Test 3: Detailed health check
        try:
            response = self.session.get(f"{self.base_url}/health/detailed")
            print(f"✅ Detailed Health Check: {response.status_code}")
            if response.status_code == 200:
                detailed_health = response.json()
                services = detailed_health.get('services', {})
                print(f"   Database: {services.get('database', 'unknown')}")
                print(f"   Redis: {services.get('redis', 'unknown')}")
                print(f"   Agents: {services.get('agents', 'unknown')}")
            else:
                print(f"⚠️  Detailed health check degraded: {response.text}")
        except Exception as e:
            print(f"⚠️  Detailed health check error: {e}")
        
        return True
    
    def start_discovery_process(self, search_query: str = None, max_results: int = 100):
        """Start the production discovery process"""
        print(f"\n🚀 Starting Production Discovery Process")
        print("=" * 50)
        
        # Default search parameters for undiscovered talent
        if search_query is None:
            search_query = "official music video"
        
        discovery_request = {
            "search_query": search_query,
            "max_results": max_results
        }
        
        print(f"🎯 Discovery Parameters:")
        print(f"   Query: {search_query}")
        print(f"   Max Results: {max_results}")
        print(f"   Timeout: {API_TIMEOUT}s")
        
        try:
            print(f"\n⏳ Sending discovery request...")
            start_time = time.time()
            
            response = self.session.post(
                f"{self.base_url}/api/master-discovery/discover",
                params=discovery_request,
                timeout=API_TIMEOUT
            )
            
            execution_time = time.time() - start_time
            print(f"⏱️  Request completed in {execution_time:.2f}s")
            print(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n🎉 Discovery Process Completed Successfully!")
                print("=" * 50)
                
                # Parse results
                data = result.get('data', {})
                artists = data.get('artists', [])
                total_found = data.get('total_found', 0)
                total_processed = data.get('total_processed', 0)
                execution_time = data.get('execution_time', 0)
                
                print(f"📈 Discovery Summary:")
                print(f"   Total Videos Processed: {total_processed}")
                print(f"   Artists Discovered: {total_found}")
                print(f"   Execution Time: {execution_time:.2f}s")
                print(f"   Success Rate: {(total_found/max(total_processed, 1)*100):.1f}%")
                
                # Show top artists found
                if artists:
                    print(f"\n🎭 Top Artists Discovered:")
                    for i, artist in enumerate(artists[:5], 1):
                        name = artist.get('name', 'Unknown')
                        score = artist.get('discovery_score', 0)
                        youtube_subs = artist.get('youtube_subscriber_count', 'N/A')
                        print(f"   {i}. {name} (Score: {score:.1f}, Subs: {youtube_subs})")
                
                # Show API metadata
                api_metadata = result.get('api_metadata', {})
                if api_metadata:
                    features = api_metadata.get('features', [])
                    print(f"\n🔧 System Features Active: {len(features)}")
                    for feature in features[:3]:
                        print(f"   • {feature}")
                
                return result
            
            else:
                print(f"❌ Discovery request failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"⏰ Discovery request timed out after {API_TIMEOUT}s")
            print("This might be normal for large discovery processes.")
            return None
        except Exception as e:
            print(f"❌ Discovery request error: {e}")
            return None
    
    def start_undiscovered_talent_discovery(self, max_results: int = 50):
        """Start specialized undiscovered talent discovery"""
        print(f"\n🌟 Starting Undiscovered Talent Discovery")
        print("=" * 50)
        print("🎯 Targeting: New artists, <50k views, last 24h uploads")
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/discover/undiscovered-talent",
                params={"max_results": max_results},
                timeout=API_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                data = result.get('data', {})
                total_found = data.get('total_found', 0)
                
                print(f"✅ Undiscovered Talent Discovery Completed!")
                print(f"   New Talents Found: {total_found}")
                
                return result
            else:
                print(f"❌ Undiscovered talent discovery failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Undiscovered talent discovery error: {e}")
            return None

def main():
    """Main production test and discovery starter"""
    print("🎵 Production Music Discovery System")
    print("🚀 Deployment Test & Discovery Starter")
    print("=" * 60)
    print(f"📅 Started at: {datetime.now()}")
    print(f"🌐 Production URL: {PRODUCTION_BASE_URL}")
    
    # Initialize tester
    tester = ProductionDiscoveryTester(PRODUCTION_BASE_URL)
    
    # Test system health
    if not tester.test_system_health():
        print("\n❌ System health check failed. Cannot proceed with discovery.")
        return
    
    print("\n✅ System is healthy and ready for discovery!")
    
    # Start discovery processes
    print("\n" + "="*60)
    print("🎯 DISCOVERY PHASE 1: General Music Discovery")
    
    # General discovery
    result1 = tester.start_discovery_process(
        search_query="official music video new artist 2024",
        max_results=100
    )
    
    print("\n" + "="*60)
    print("🌟 DISCOVERY PHASE 2: Undiscovered Talent")
    
    # Undiscovered talent discovery
    result2 = tester.start_undiscovered_talent_discovery(max_results=50)
    
    print("\n" + "="*60)
    print("🎉 PRODUCTION DISCOVERY COMPLETE!")
    print("=" * 60)
    
    if result1 or result2:
        print("✅ At least one discovery process completed successfully")
        print("📊 Check your Supabase database for discovered artists")
        print("🌐 Visit your frontend dashboard to explore results")
    else:
        print("⚠️  Discovery processes encountered issues")
        print("🔧 Check logs and system status for troubleshooting")
    
    print(f"\n📅 Completed at: {datetime.now()}")

if __name__ == "__main__":
    # Update the PRODUCTION_BASE_URL with your actual Coolify domain
    print("🔧 Before running, update PRODUCTION_BASE_URL in this script!")
    print("💡 Example: https://music-discovery.your-domain.com")
    
    # Uncomment the line below once you've updated the URL
    # main()
    
    print("✅ Ready for production deployment testing!") 