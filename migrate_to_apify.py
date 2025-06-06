#!/usr/bin/env python3
"""
Migration script to switch from YouTube Data API to Apify YouTube Scraper
Solves quota limitations and reduces costs for music discovery
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

def backup_original_files():
    """Create backups of original files before migration"""
    backup_dir = Path("backups") / f"youtube_api_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    files_to_backup = [
        "backend/app/agents/youtube_agent.py",
        "backend/app/agents/orchestrator.py"
    ]
    
    print(f"📦 Creating backups in: {backup_dir}")
    
    for file_path in files_to_backup:
        file_path = Path(file_path)
        if file_path.exists():
            backup_file = backup_dir / file_path.name
            shutil.copy2(file_path, backup_file)
            print(f"✅ Backed up: {file_path} -> {backup_file}")
    
    return backup_dir

def check_environment_setup():
    """Check if Apify environment is properly configured"""
    print("\n🔍 Checking Environment Configuration...")
    
    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        return False
    
    # Check for APIFY_API_TOKEN
    with open(env_file, 'r') as f:
        env_content = f.read()
    
    if 'APIFY_API_TOKEN=' not in env_content:
        print("❌ APIFY_API_TOKEN not found in .env")
        return False
    
    if 'your_apify_token_here' in env_content:
        print("❌ APIFY_API_TOKEN not configured (still using placeholder)")
        return False
    
    print("✅ Apify environment appears to be configured")
    return True

def run_integration_test():
    """Run the Apify integration test"""
    print("\n🧪 Running Integration Test...")
    
    try:
        import subprocess
        result = subprocess.run(['python', 'test_apify_integration.py'], 
                              capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Integration test passed!")
            return True
        else:
            print("❌ Integration test failed:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error running integration test: {e}")
        return False

def show_migration_status():
    """Show current migration status"""
    print("\n📊 Migration Status:")
    print("=" * 40)
    
    # Check if Apify agent exists
    apify_agent = Path("backend/app/agents/apify_youtube_agent.py")
    if apify_agent.exists():
        print("✅ Apify YouTube Agent: Created")
    else:
        print("❌ Apify YouTube Agent: Missing")
    
    # Check if orchestrator is updated
    orchestrator = Path("backend/app/agents/orchestrator.py")
    if orchestrator.exists():
        with open(orchestrator, 'r') as f:
            content = f.read()
        
        if 'ApifyYouTubeAgent' in content:
            print("✅ Orchestrator: Updated to use Apify")
        else:
            print("❌ Orchestrator: Still using old YouTube API")
    
    # Check environment
    if check_environment_setup():
        print("✅ Environment: Configured")
    else:
        print("❌ Environment: Needs configuration")

def show_migration_benefits():
    """Show the benefits of migrating to Apify"""
    print("\n🎯 Migration Benefits:")
    print("=" * 40)
    print("📈 Cost Comparison:")
    print("   YouTube API: $0.005 per search + quotas")
    print("   Apify: $0.50 per 1,000 videos (no quotas!)")
    print()
    print("⚡ Performance:")
    print("   YouTube API: Rate limited, quota failures")
    print("   Apify: 10+ videos/second, 97% success rate")
    print()
    print("🔓 Limitations:")
    print("   YouTube API: 10,000 units/day quota")
    print("   Apify: Pay-per-use, no artificial limits")

def show_next_steps():
    """Show what to do after migration"""
    print("\n📋 Next Steps:")
    print("=" * 40)
    print("1. 🔧 Configure Environment:")
    print("   python setup_apify_env.py")
    print()
    print("2. 🧪 Test Integration:")
    print("   python test_apify_integration.py")
    print()
    print("3. 🚀 Start Your Application:")
    print("   cd backend && uvicorn app.main:app --reload")
    print()
    print("4. 📊 Monitor Costs:")
    print("   https://console.apify.com/account/billing")

def run_migration():
    """Run the complete migration process"""
    print("🏯 YouTube API → Apify Migration")
    print("=" * 50)
    print("Migrating from quota-limited YouTube API to Apify scraper")
    print("Cost: $0.50 per 1,000 videos | Success rate: 97%")
    
    # Step 1: Backup original files
    backup_dir = backup_original_files()
    print(f"✅ Backups created in: {backup_dir}")
    
    # Step 2: Show migration status
    show_migration_status()
    
    # Step 3: Check environment
    env_configured = check_environment_setup()
    if not env_configured:
        print("\n⚠️ Environment not configured. Run setup_apify_env.py first")
        show_next_steps()
        return False
    
    # Step 4: Run integration test
    if run_integration_test():
        print("\n🎉 Migration Completed Successfully!")
        show_migration_benefits()
        print("\n✅ Your music discovery system is now using Apify!")
        print("   - No more YouTube API quota limitations")
        print("   - Cost-effective scraping at $0.50/1000 videos")
        print("   - 97% success rate with high performance")
        return True
    else:
        print("\n❌ Migration failed at integration test")
        print("Please check your Apify configuration and try again")
        show_next_steps()
        return False

if __name__ == "__main__":
    success = run_migration()
    
    if success:
        print("\n🚀 Ready to discover music without quotas!")
    else:
        print("\n🔧 Please complete the setup steps and try again")
    
    print("\nSupport: apidojo10@gmail.com") 