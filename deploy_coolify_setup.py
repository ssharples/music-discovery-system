#!/usr/bin/env python3
"""
Coolify Deployment Setup Script for Apify Integration
Helps configure environment variables and validate deployment
"""

import os
import json
import requests
from pathlib import Path

def check_apify_token_validity(token):
    """Validate Apify API token by making a test request"""
    try:
        url = "https://api.apify.com/v2/users/me"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            user_data = response.json()['data']
            return True, user_data.get('username', 'Unknown')
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def show_coolify_environment_variables():
    """Display environment variables needed for Coolify"""
    
    print("🔧 Coolify Environment Variables Setup")
    print("=" * 50)
    print()
    print("Add these environment variables in your Coolify dashboard:")
    print()
    
    # Required for Apify
    print("📋 REQUIRED - Apify Integration:")
    print("APIFY_API_TOKEN=your_apify_token_here")
    print()
    
    # Existing variables
    print("📋 EXISTING Environment Variables:")
    env_vars = [
        ("ENVIRONMENT", "production"),
        ("DEBUG", "false"),
        ("SECRET_KEY", "your_secret_key_here"),
        ("ALLOWED_ORIGINS", "https://yourdomain.com"),
        ("SUPABASE_URL", "your_supabase_url"),
        ("SUPABASE_KEY", "your_supabase_key"),
        ("DEEPSEEK_API_KEY", "your_deepseek_key"),
        ("SPOTIFY_CLIENT_ID", "your_spotify_client_id"),
        ("SPOTIFY_CLIENT_SECRET", "your_spotify_client_secret"),
        ("FIRECRAWL_API_KEY", "your_firecrawl_key"),
        ("YOUTUBE_API_KEY", "optional_youtube_key"),
        ("SENTRY_DSN", "optional_sentry_dsn")
    ]
    
    for var, example in env_vars:
        print(f"{var}={example}")
    print()

def test_deployment_readiness():
    """Test if deployment files are ready"""
    
    print("🧪 Deployment Readiness Check")
    print("=" * 40)
    
    # Check critical files
    files_to_check = [
        ("docker-compose.yml", "Docker Compose configuration"),
        ("backend/app/agents/apify_youtube_agent.py", "Apify YouTube Agent"),
        ("backend/app/agents/orchestrator.py", "Updated Orchestrator"),
        ("backend/requirements.txt", "Python dependencies")
    ]
    
    all_ready = True
    
    for file_path, description in files_to_check:
        if Path(file_path).exists():
            print(f"✅ {description}: Found")
        else:
            print(f"❌ {description}: Missing ({file_path})")
            all_ready = False
    
    # Check docker-compose.yml for Apify token
    docker_compose = Path("docker-compose.yml")
    if docker_compose.exists():
        with open(docker_compose, 'r') as f:
            content = f.read()
        
        if 'APIFY_API_TOKEN' in content:
            print("✅ Docker Compose: Configured for Apify")
        else:
            print("❌ Docker Compose: Missing APIFY_API_TOKEN")
            all_ready = False
    
    print()
    if all_ready:
        print("🎉 Deployment is ready!")
    else:
        print("⚠️ Some files need attention before deployment")
    
    return all_ready

def show_cost_estimates():
    """Show cost estimates for different usage levels"""
    
    print("💰 Apify Cost Estimates")
    print("=" * 30)
    print()
    
    scenarios = [
        ("Light Usage", 500, "~10 discovery sessions/day"),
        ("Medium Usage", 2000, "~40 discovery sessions/day"),
        ("Heavy Usage", 10000, "~200 discovery sessions/day")
    ]
    
    for scenario, videos_per_day, description in scenarios:
        daily_cost = (videos_per_day / 1000) * 0.50
        monthly_cost = daily_cost * 30
        
        print(f"📊 {scenario}:")
        print(f"   {description}")
        print(f"   Videos/day: {videos_per_day:,}")
        print(f"   Cost/day: ${daily_cost:.2f}")
        print(f"   Cost/month: ${monthly_cost:.2f}")
        print()
    
    print("💡 Compare to YouTube API quota overages (often $100+/month)")

def show_deployment_steps():
    """Show step-by-step deployment instructions"""
    
    print("🚀 Coolify Deployment Steps")
    print("=" * 35)
    print()
    
    steps = [
        "1. Get Apify API Token",
        "   → Go to: https://console.apify.com/account/integrations",
        "   → Copy your API token",
        "",
        "2. Add Environment Variables in Coolify",
        "   → Navigate to your application in Coolify",
        "   → Go to Environment Variables section",
        "   → Add: APIFY_API_TOKEN=your_token_here",
        "   → Verify all other variables are set",
        "",
        "3. Deploy Updated Application",
        "   → Commit updated docker-compose.yml to git",
        "   → Push changes to your repository",
        "   → Trigger deployment in Coolify",
        "",
        "4. Verify Deployment",
        "   → Check application logs for Apify activity",
        "   → Test music discovery functionality",
        "   → Monitor costs in Apify console"
    ]
    
    for step in steps:
        print(step)
    print()

def validate_apify_setup():
    """Interactive Apify token validation"""
    
    print("🔍 Apify Token Validation")
    print("=" * 30)
    
    token = input("Enter your Apify API token (or 'skip' to continue): ").strip()
    
    if token.lower() == 'skip':
        print("⏭️ Skipping token validation")
        return False
    
    if not token:
        print("❌ No token provided")
        return False
    
    print("🧪 Testing token validity...")
    
    is_valid, result = check_apify_token_validity(token)
    
    if is_valid:
        print(f"✅ Token is valid! Account: {result}")
        print(f"💡 Add this to Coolify: APIFY_API_TOKEN={token}")
        return True
    else:
        print(f"❌ Token validation failed: {result}")
        print("Please check your token and try again")
        return False

def main():
    """Main setup function"""
    
    print("🏯 Coolify + Apify Deployment Setup")
    print("=" * 45)
    print("Setting up Apify YouTube integration for Coolify deployment")
    print()
    
    # Step 1: Check deployment readiness
    is_ready = test_deployment_readiness()
    
    if not is_ready:
        print("❌ Please fix missing files before deployment")
        return
    
    # Step 2: Show environment variables
    show_coolify_environment_variables()
    
    # Step 3: Validate Apify token (optional)
    token_valid = validate_apify_setup()
    
    # Step 4: Show costs
    show_cost_estimates()
    
    # Step 5: Show deployment steps
    show_deployment_steps()
    
    # Final summary
    print("📋 Summary")
    print("=" * 15)
    
    if token_valid:
        print("✅ Apify token validated")
    else:
        print("⚠️ Apify token not validated (add it manually)")
    
    print("✅ Deployment files ready")
    print("✅ Cost estimates provided")
    print("✅ Environment variables listed")
    print()
    print("🚀 Ready for Coolify deployment!")
    print()
    print("Next steps:")
    print("1. Add APIFY_API_TOKEN to Coolify environment variables")
    print("2. Commit and push your code changes")
    print("3. Deploy via Coolify")
    print("4. Monitor Apify costs at: https://console.apify.com/account/billing")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Setup error: {e}")
        print("Please check your configuration and try again") 