#!/usr/bin/env python3
"""
Start the music discovery system and run test API calls.
"""

import asyncio
import json
import time
import sys
from pathlib import Path
import subprocess
import requests
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

def start_server():
    """Start the FastAPI server"""
    print("🚀 Starting FastAPI server...")
    
    try:
        # Start server in background
        cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        print("⏳ Waiting for server to start...")
        time.sleep(8)
        
        # Check if server is running
        try:
            response = requests.get("http://localhost:8000/docs", timeout=5)
            if response.status_code == 200:
                print("✅ Server started successfully!")
                return process
            else:
                print(f"❌ Server returned status code: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Server not responding: {e}")
            return None
            
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None

def test_api_endpoints():
    """Test the music discovery API endpoints"""
    print("\n🧪 Testing API Endpoints")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Health check
    print("\n📋 Test 1: Health Check")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
            print("✅ Health check passed")
        else:
            print("❌ Health check failed")
    except Exception as e:
        print(f"❌ Health check error: {e}")
    
    # Test 2: Master Discovery Status
    print("\n📋 Test 2: Master Discovery Status")
    try:
        response = requests.get(f"{base_url}/api/master-discovery/status", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            print("✅ Master discovery status check passed")
        else:
            print("❌ Master discovery status check failed")
    except Exception as e:
        print(f"❌ Master discovery status error: {e}")
    
    # Test 3: Discovery Request
    print("\n📋 Test 3: Small Discovery Request")
    try:
        discovery_request = {
            "search_query": "official music video new artist 2024",
            "max_results": 2,  # Small test
            "quality_threshold": 0.3
        }
        
        print(f"Request: {json.dumps(discovery_request, indent=2)}")
        
        response = requests.post(
            f"{base_url}/api/master-discovery/discover",
            json=discovery_request,
            timeout=60  # Longer timeout for discovery
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            print("✅ Discovery request completed successfully!")
            
            # Show summary
            if 'artists' in result:
                print(f"\n📊 Discovery Summary:")
                print(f"- Found {len(result['artists'])} artists")
                for i, artist in enumerate(result['artists'][:3]):  # Show first 3
                    print(f"  {i+1}. {artist.get('name', 'Unknown')} - {artist.get('video_metadata', {}).get('view_count', 'N/A')} views")
        else:
            print(f"❌ Discovery request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Discovery request error: {e}")

def main():
    """Main function"""
    print("🎵 Music Discovery System - Local Deployment Test")
    print("=" * 60)
    print(f"📅 Started at: {datetime.now()}")
    
    # Start server
    server_process = start_server()
    
    if server_process is None:
        print("❌ Could not start server. Exiting.")
        return
    
    try:
        # Test API endpoints
        test_api_endpoints()
        
        print("\n🎉 Testing completed!")
        print("\n🌐 You can also visit: http://localhost:8000/docs for interactive API documentation")
        
        # Keep server running
        print("\n⏸️  Server is running. Press Ctrl+C to stop...")
        server_process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        server_process.terminate()
        server_process.wait()
        print("✅ Server stopped.")
    
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    main() 