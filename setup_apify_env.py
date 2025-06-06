#!/usr/bin/env python3
"""
Environment setup helper for Apify YouTube integration
Run this to check and set up the APIFY_API_TOKEN environment variable
"""

import os
from pathlib import Path

def setup_apify_environment():
    """Set up Apify environment configuration"""
    
    print("🔧 Apify Environment Setup")
    print("=" * 40)
    
    # Check if .env file exists
    env_file = Path(".env")
    
    print(f"📁 Looking for .env file: {env_file.absolute()}")
    
    if not env_file.exists():
        print("❌ .env file not found!")
        print("Creating .env file template...")
        
        env_template = """# Apify Configuration
APIFY_API_TOKEN=your_apify_token_here

# Existing environment variables (add your existing ones here)
# OPENAI_API_KEY=your_openai_key
# DEEPSEEK_API_KEY=your_deepseek_key
# SPOTIFY_CLIENT_ID=your_spotify_client_id
# SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
# FIRECRAWL_API_KEY=your_firecrawl_key
# SUPABASE_URL=your_supabase_url
# SUPABASE_KEY=your_supabase_key
"""
        
        with open(env_file, 'w') as f:
            f.write(env_template)
        
        print(f"✅ Created .env template at: {env_file.absolute()}")
        print()
        print("Next steps:")
        print("1. Get your Apify API token from: https://console.apify.com/account/integrations")
        print("2. Replace 'your_apify_token_here' in .env with your actual token")
        print("3. Add your other API keys to the .env file")
        return False
    
    # Check if APIFY_API_TOKEN is set
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    if 'APIFY_API_TOKEN=' in env_content:
        # Check if it's still the placeholder
        if 'your_apify_token_here' in env_content:
            print("⚠️ APIFY_API_TOKEN found but not configured!")
            print("Please replace 'your_apify_token_here' with your actual Apify API token")
            print()
            print("Get your token from: https://console.apify.com/account/integrations")
            return False
        else:
            print("✅ APIFY_API_TOKEN is configured in .env")
            
            # Load and check the token
            from dotenv import load_dotenv
            load_dotenv()
            
            token = os.getenv('APIFY_API_TOKEN')
            if token and len(token) > 10:  # Basic validation
                print(f"✅ Token loaded: {token[:10]}...")
                return True
            else:
                print("❌ Token appears to be invalid or empty")
                return False
    else:
        print("⚠️ APIFY_API_TOKEN not found in .env")
        print("Adding APIFY_API_TOKEN to .env...")
        
        with open(env_file, 'a') as f:
            f.write('\n# Apify Configuration\n')
            f.write('APIFY_API_TOKEN=your_apify_token_here\n')
        
        print("✅ Added APIFY_API_TOKEN to .env")
        print("Please replace 'your_apify_token_here' with your actual token")
        return False

def show_setup_instructions():
    """Show complete setup instructions"""
    print()
    print("📋 Complete Apify Integration Setup:")
    print("=" * 40)
    print()
    print("1. Get Apify API Token:")
    print("   - Go to: https://apify.com/")
    print("   - Sign up for a free account")
    print("   - Visit: https://console.apify.com/account/integrations")
    print("   - Copy your API token")
    print()
    print("2. Configure Environment:")
    print("   - Add APIFY_API_TOKEN=your_actual_token to .env")
    print("   - Save the file")
    print()
    print("3. Test Integration:")
    print("   - Run: python test_apify_integration.py")
    print()
    print("4. Update Your Application:")
    print("   - The orchestrator is already updated to use Apify")
    print("   - Start your application and test music discovery")
    print()
    print("💰 Cost Information:")
    print("   - Apify YouTube Scraper: $0.50 per 1,000 videos")
    print("   - Much cheaper than YouTube API quota issues!")
    print("   - Monitor costs at: https://console.apify.com/account/billing")

if __name__ == "__main__":
    print("🏯 Apify YouTube Scraper Setup")
    print()
    
    is_configured = setup_apify_environment()
    
    if is_configured:
        print()
        print("🎉 Apify is configured and ready!")
        print("You can now run: python test_apify_integration.py")
    else:
        show_setup_instructions()
    
    print()
    print("For support: apidojo10@gmail.com") 